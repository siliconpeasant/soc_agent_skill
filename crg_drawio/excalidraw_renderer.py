"""
Excalidraw JSON 渲染器 —— 手绘风格时钟树图

输出格式：.excalidraw（可直接拖拽到 https://excalidraw.com）
"""
import json
import uuid
from typing import Dict, List, Tuple
from .graph import Graph, Node


# 节点颜色映射（手绘风格）
NODE_COLORS = {
    "source_input":   {"bg": "#69db7c", "stroke": "#2f9e44"},
    "source_internal":{"bg": "#adb5bd", "stroke": "#495057"},
    "na":             {"bg": "#ffa94d", "stroke": "#e8590c"},
    "output":         {"bg": "#74c0fc", "stroke": "#1971c2"},
    "mux":            {"bg": "#e599f7", "stroke": "#9c36b5"},
    "div":            {"bg": "#f8f9fa", "stroke": "#343a40"},
    "icg":            {"bg": "#b2f2bb", "stroke": "#2f9e44"},
    "icg_off":        {"bg": "#e9ecef", "stroke": "#868e96"},
    "occ":            {"bg": "#e5dbff", "stroke": "#7048e8"},
    "reg":            {"bg": "#d0ebff", "stroke": "#1971c2"},
    "soft":           {"bg": "#fff3bf", "stroke": "#f08c00"},
    "rst_and":        {"bg": "#ffe066", "stroke": "#e67700"},
    "and":            {"bg": "#ffe066", "stroke": "#e67700"},
    "ctrl":           {"bg": "transparent", "stroke": "#343a40"},
}

# 边颜色调色板
EDGE_COLORS = [
    "#e03131", "#1971c2", "#2f9e44", "#f08c00",
    "#9c36b5", "#0ca678", "#c2255c", "#e8590c",
    "#0b7285", "#66a80f", "#d9480f", "#5c3a21",
]


def _uid() -> str:
    return str(uuid.uuid4())


def _get_node_colors(node_type: str, attr: str = "") -> Dict[str, str]:
    if node_type == "soft" and attr:
        if attr.upper() == "Y":
            return {"bg": "#b2f2bb", "stroke": "#2f9e44"}
        elif attr.upper() == "N":
            return {"bg": "#e9ecef", "stroke": "#868e96"}
    return NODE_COLORS.get(node_type, NODE_COLORS["output"])


class ExcalidrawRenderer:
    def __init__(self):
        self.elements: List[Dict] = []

    def render(self, graph: Graph, output_path: str, title: str = "CRG Clock Tree"):
        """自动判断树类型，调用对应渲染器"""
        is_reset = any(n.node_type in ("reg", "soft") for n in graph.nodes.values())
        if is_reset:
            self.render_reset_tree(graph, output_path, title)
        else:
            self.render_clock_tree(graph, output_path, title)

    def render_clock_tree(self, graph: Graph, output_path: str, title: str = "CRG Clock Tree"):
        """渲染时钟树 Excalidraw"""
        self.elements = []
        self._add_clock_title(title, graph)
        self._render_elements(graph)
        self._write(output_path)

    def render_reset_tree(self, graph: Graph, output_path: str, title: str = "CRG Reset Tree"):
        """渲染复位树 Excalidraw"""
        self.elements = []
        self._add_reset_title(title, graph)
        self._render_elements(graph)
        self._write(output_path)

    def _render_elements(self, graph: Graph):
        """通用元素渲染：节点 + 边"""
        # 节点 → rectangle + text
        node_id_map: Dict[str, str] = {}
        for name, node in graph.nodes.items():
            eid = self._add_node(node)
            node_id_map[name] = eid

        # 构建源头索引映射（用于边颜色分配）
        source_names = sorted({
            n.name for n in graph.nodes.values()
            if n.node_type.startswith("source")
        })
        source_index_map = {name: i for i, name in enumerate(source_names)}

        # 预先为门控节点（MUX / rst_and）的输入边分配 entry 点
        gate_entry_map = {}  # (src, dst) -> entry_y_offset（相对于节点顶部）
        for dst_name, node in graph.nodes.items():
            if node.node_type not in ("mux", "rst_and"):
                continue
            inputs = [src for src, d in graph.edges if d == dst_name]
            for i, src in enumerate(inputs):
                if node.node_type == "mux":
                    # MUX 高 40：src0 接 1/4 处，src1 接 3/4 处
                    gate_entry_map[(src, dst_name)] = 10 if i == 0 else 30
                elif node.node_type == "rst_and":
                    # rst_and 高 60：SRC0 接 1/4 处，外部输入接 3/4 处
                    gate_entry_map[(src, dst_name)] = 15 if i == 0 else 45

        # 边 → arrow（source 出边独立车道错开）
        source_edges = {}
        for src, dst in graph.edges:
            if graph.nodes[src].node_type.startswith("source"):
                source_edges.setdefault(src, []).append((src, dst))

        # Source 出边（带车道偏移）
        for src_name, edges in source_edges.items():
            idx = source_index_map.get(src_name, 0)
            for src, dst in edges:
                if src not in node_id_map or dst not in node_id_map:
                    continue
                src_node = graph.nodes[src]
                dst_node = graph.nodes[dst]
                root_src = self._get_root_source(graph, src)
                stroke = EDGE_COLORS[source_index_map.get(root_src, 0) % len(EDGE_COLORS)]
                entry_offset = gate_entry_map.get((src, dst))
                self._add_arrow_source(node_id_map[src], node_id_map[dst], src_node, dst_node, stroke, idx, entry_offset)

        # 中间节点边
        for src, dst in graph.edges:
            if graph.nodes[src].node_type.startswith("source"):
                continue
            if src not in node_id_map or dst not in node_id_map:
                continue
            src_node = graph.nodes[src]
            dst_node = graph.nodes[dst]
            root_src = self._get_root_source(graph, src)
            stroke = EDGE_COLORS[source_index_map.get(root_src, 0) % len(EDGE_COLORS)]
            entry_offset = gate_entry_map.get((src, dst))
            self._add_arrow(node_id_map[src], node_id_map[dst], src_node, dst_node, stroke, entry_offset)

    def _write(self, output_path: str):
        """写入 Excalidraw JSON 文件"""
        scene = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": self.elements,
            "appState": {"viewBackgroundColor": "#ffffff"},
            "files": {},
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(scene, f, indent=2, ensure_ascii=False)

        print(f"Saved: {output_path}")

    def _add_clock_title(self, title: str, graph: Graph):
        """时钟树标题"""
        sources = sum(1 for n in graph.nodes.values() if n.node_type.startswith("source"))
        outputs = sum(1 for n in graph.nodes.values() if n.node_type == "output")
        divs = sum(1 for n in graph.nodes.values() if n.node_type == "div")
        icgs = sum(1 for n in graph.nodes.values() if n.node_type in ("icg", "icg_off"))
        occs = sum(1 for n in graph.nodes.values() if n.node_type == "occ")
        text = f"{title}\n{sources} sources  |  {outputs} outputs  |  {divs} DIV  |  {icgs} ICG  |  {occs} OCC"
        self._append_title(text)

    def _add_reset_title(self, title: str, graph: Graph):
        """复位树标题"""
        sources = sum(1 for n in graph.nodes.values() if n.node_type.startswith("source"))
        outputs = sum(1 for n in graph.nodes.values() if n.node_type == "output")
        regs = sum(1 for n in graph.nodes.values() if n.node_type == "reg")
        softs = sum(1 for n in graph.nodes.values() if n.node_type == "soft")
        text = f"{title}\n{sources} sources  |  {outputs} outputs  |  {regs} REG  |  {softs} SOFT"
        self._append_title(text)

    def _append_title(self, text: str):
        """添加标题文本元素"""
        self.elements.append({
            "id": _uid(),
            "type": "text",
            "x": 80,
            "y": 30,
            "width": 600,
            "height": 50,
            "text": text,
            "originalText": text,
            "fontSize": 18,
            "fontFamily": 1,
            "textAlign": "left",
            "verticalAlign": "top",
            "strokeColor": "#1e1e1e",
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 1,
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "boundElements": [],
            "seed": 1,
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
        })

    def _get_node_size(self, node: Node) -> Tuple[int, int]:
        """根据节点类型返回 (width, height)"""
        if node.node_type.startswith("source"):
            return (200, 40)
        elif node.node_type == "mux":
            return (100, 40)
        elif node.node_type == "rst_and":
            return (40, 60)
        elif node.node_type == "reg":
            return (120, 40)
        elif node.node_type == "soft":
            return (100, 40)
        elif node.node_type in ("icg", "icg_off"):
            return (80, 40)
        elif node.node_type == "occ":
            return (80, 40)
        elif node.node_type == "div":
            return (100, 40)
        else:
            return (220, 40)

    def _add_node(self, node: Node) -> str:
        eid = _uid()
        colors = _get_node_colors(node.node_type, node.attr)
        w, h = self._get_node_size(node)

        # 矩形
        self.elements.append({
            "id": eid,
            "type": "rectangle",
            "x": node.x,
            "y": node.y,
            "width": w,
            "height": h,
            "strokeColor": colors["stroke"],
            "backgroundColor": colors["bg"],
            "fillStyle": "solid",
            "strokeWidth": 2,
            "roughness": 1,
            "opacity": 100,
            "roundness": {"type": 3},
            "groupIds": [],
            "boundElements": [{"type": "text", "id": f"{eid}-label"}],
            "seed": hash(node.name) % 10000,
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
        })

        # 文字标签
        display = self._get_display_text(node)
        self.elements.append({
            "id": f"{eid}-label",
            "type": "text",
            "x": node.x + 10,
            "y": node.y + 10,
            "width": w - 20,
            "height": h - 20,
            "text": display,
            "originalText": display,
            "fontSize": 11,
            "fontFamily": 1,
            "textAlign": "center",
            "verticalAlign": "middle",
            "containerId": eid,
            "strokeColor": "#1e1e1e",
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 1,
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "boundElements": [],
            "seed": hash(node.name) % 10000 + 1,
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
        })

        return eid

    def _add_arrow_source(self, src_eid: str, dst_eid: str, src_node: Node, dst_node: Node, stroke_color: str, lane_idx: int, entry_y_offset: float = None):
        """Source 出边：水平出发，独立车道错开，最终连到目标节点左侧"""
        src_w, src_h = self._get_node_size(src_node)
        src_right = src_node.x + src_w
        src_center_y = src_node.y + src_h / 2
        bus_x = src_right + 5 + lane_idx * 10

        dst_w, dst_h = self._get_node_size(dst_node)
        dst_left = dst_node.x
        if entry_y_offset is not None:
            dst_y = dst_node.y + entry_y_offset
        else:
            dst_y = dst_node.y + dst_h / 2

        dx = dst_left - src_right
        dy = dst_y - src_center_y

        # 正交布线：水平到 bus_x → 垂直到目标 Y → 水平到目标左侧
        points = [
            [0, 0],
            [bus_x - src_right, 0],
            [bus_x - src_right, dy],
            [dx, dy],
        ]

        self.elements.append({
            "id": _uid(),
            "type": "arrow",
            "x": src_right,
            "y": src_center_y,
            "width": abs(dx),
            "height": abs(dy),
            "points": points,
            "strokeColor": stroke_color,
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 2,
            "roughness": 1,
            "opacity": 100,
            "endArrowhead": "arrow",
            "groupIds": [],
            "boundElements": [],
            "seed": hash(src_node.name + dst_node.name) % 10000,
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
        })

    def _add_arrow(self, src_eid: str, dst_eid: str, src_node: Node, dst_node: Node, stroke_color: str, entry_y_offset: float = None):
        """中间节点边：从源节点右侧中心出发，连到目标节点左侧"""
        src_w, src_h = self._get_node_size(src_node)
        start_x = src_node.x + src_w
        start_y = src_node.y + src_h / 2

        dst_w, dst_h = self._get_node_size(dst_node)
        end_x = dst_node.x
        if entry_y_offset is not None:
            end_y = dst_node.y + entry_y_offset
        else:
            end_y = dst_node.y + dst_h / 2

        dx = end_x - start_x
        dy = end_y - start_y

        # 正交布线
        if abs(dx) < 2:
            points = [[0, 0], [0, dy]]
        else:
            points = [[0, 0], [0, dy], [dx, dy]]

        self.elements.append({
            "id": _uid(),
            "type": "arrow",
            "x": start_x,
            "y": start_y,
            "width": abs(dx),
            "height": abs(dy),
            "points": points,
            "strokeColor": stroke_color,
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 2,
            "roughness": 1,
            "opacity": 100,
            "endArrowhead": "arrow",
            "groupIds": [],
            "boundElements": [],
            "seed": hash(src_node.name + dst_node.name) % 10000,
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
        })

    def _get_display_text(self, node: Node) -> str:
        if node.node_type == "mux":
            return node.attr if node.attr else "MUX"
        elif node.node_type == "rst_and":
            return node.attr if node.attr else "&"
        elif node.node_type == "div":
            return node.attr if node.attr else "DIV"
        elif node.node_type in ("icg", "icg_off"):
            return node.attr if node.attr else "ICG"
        elif node.node_type == "occ":
            return node.attr if node.attr else "OCC"
        elif node.node_type == "reg":
            return node.attr if node.attr else "REG"
        elif node.node_type == "soft":
            return "SOFT"
        elif node.node_type == "and":
            return node.attr if node.attr else "&"
        elif node.node_type == "ctrl":
            return node.attr if node.attr else ""
        else:
            return node.name

    def _get_root_source(self, graph: Graph, node_name: str) -> str:
        visited = set()
        current = node_name
        while current in graph.nodes:
            if current in visited:
                break
            visited.add(current)
            node = graph.nodes[current]
            if node.node_type.startswith("source"):
                return current
            prev = [s for s, d in graph.edges if d == current]
            if not prev:
                break
            current = prev[0]
        return current
