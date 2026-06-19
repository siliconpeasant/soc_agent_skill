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
    "source_input":   {"bg": "#16a34a", "stroke": "#15803d"},
    "source_internal":{"bg": "#adb5bd", "stroke": "#495057"},
    "reset_source":   {"bg": "#f0fdf4", "stroke": "#22c55e"},
    "na":             {"bg": "#ffa94d", "stroke": "#e8590c"},
    "output":         {"bg": "#eff6ff", "stroke": "#38bdf8"},
    "mux":            {"bg": "#e599f7", "stroke": "#9c36b5"},
    "div":            {"bg": "#f8f9fa", "stroke": "#343a40"},
    "icg":            {"bg": "#b2f2bb", "stroke": "#2f9e44"},
    "icg_off":        {"bg": "#e9ecef", "stroke": "#868e96"},
    "occ":            {"bg": "#e5dbff", "stroke": "#7048e8"},
    "reg":            {"bg": "#d0ebff", "stroke": "#1971c2"},
    "soft":           {"bg": "#fff3bf", "stroke": "#f08c00"},
    "rst_and":        {"bg": "#fff7ed", "stroke": "#f97316"},
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
        is_reset = (
            getattr(graph, "tree_type", "") == "reset"
            or any(n.node_type in ("reg", "soft", "rst_and", "reset_source") for n in graph.nodes.values())
        )
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
        self._add_reset_structure(graph)
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
                    # rst_and 高 60：SRC0 接上半部，局部复位源分散接入下半部
                    if i == 0:
                        gate_entry_map[(src, dst_name)] = 15
                    else:
                        extra_count = max(len(inputs) - 1, 1)
                        if extra_count == 1:
                            gate_entry_map[(src, dst_name)] = 45
                        else:
                            gate_entry_map[(src, dst_name)] = 35 + (i - 1) * (20 / (extra_count - 1))

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
            if src_node.node_type == "reset_source":
                stroke = "#22c55e"
            else:
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
        reset_sources = sum(1 for n in graph.nodes.values() if n.node_type == "reset_source")
        outputs = sum(1 for n in graph.nodes.values() if n.node_type == "output")
        regs = sum(1 for n in graph.nodes.values() if n.node_type == "reg")
        softs = sum(1 for n in graph.nodes.values() if n.node_type == "soft")
        ands = sum(1 for n in graph.nodes.values() if n.node_type == "rst_and")
        text = (
            f"{title}\n"
            f"{sources} root sources  |  {reset_sources} local sources  |  "
            f"{outputs} outputs  |  {ands} AND  |  {regs} REG  |  {softs} SOFT"
        )
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

    def _add_reset_structure(self, graph: Graph):
        cols = self._get_reset_columns(graph)
        if not cols:
            return
        band_y = 92
        for label, x, width, _color in cols:
            self.elements.append({
                "id": _uid(),
                "type": "text",
                "x": x,
                "y": band_y - 24,
                "width": width,
                "height": 20,
                "text": label,
                "originalText": label,
                "fontSize": 11,
                "fontFamily": 1,
                "textAlign": "center",
                "verticalAlign": "middle",
                "strokeColor": "#64748b",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "roughness": 0,
                "opacity": 100,
                "groupIds": [],
                "boundElements": [],
                "seed": 1,
                "version": 1,
                "versionNonce": 1,
                "isDeleted": False,
            })
        self._add_reset_row_labels(graph)

    def _get_reset_columns(self, graph: Graph):
        root_nodes = [n for n in graph.nodes.values() if n.node_type.startswith("source")]
        local_nodes = [n for n in graph.nodes.values() if n.node_type == "reset_source"]
        gates = [n for n in graph.nodes.values() if n.node_type == "rst_and"]
        outputs = [n for n in graph.nodes.values() if n.node_type == "output"]
        if not (root_nodes and gates and outputs):
            return []
        root_x = min(n.x for n in root_nodes) - 20
        local_x = min((n.x for n in local_nodes), default=root_x + 300) - 20
        gate_x = min(n.x for n in gates) - 18
        output_x = min(n.x for n in outputs) - 20
        return [
            ("ROOT RESET", root_x, 240, "#f8fafc"),
            ("LOCAL RESET SOURCES", local_x, 220, "#f0fdf4"),
            ("COMBINE", gate_x, 86, "#fff7ed"),
            ("RESET OUTPUTS", output_x, 260, "#eff6ff"),
        ]

    def _add_reset_row_labels(self, graph: Graph):
        local_nodes = [n for n in graph.nodes.values() if n.node_type == "reset_source"]
        outputs = [n for n in graph.nodes.values() if n.node_type == "output"]
        if not (local_nodes and outputs):
            return
        label_x = min(n.x for n in local_nodes) - 82
        for output in sorted(outputs, key=lambda n: n.order):
            domain = self._reset_domain_label(output.name)
            self.elements.append({
                "id": _uid(),
                "type": "text",
                "x": label_x,
                "y": output.y + 10,
                "width": 60,
                "height": 18,
                "text": domain,
                "originalText": domain,
                "fontSize": 10,
                "fontFamily": 1,
                "textAlign": "right",
                "verticalAlign": "middle",
                "strokeColor": "#94a3b8",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "roughness": 0,
                "opacity": 100,
                "groupIds": [],
                "boundElements": [],
                "seed": 1,
                "version": 1,
                "versionNonce": 1,
                "isDeleted": False,
            })

    @staticmethod
    def _reset_domain_label(name: str) -> str:
        for suffix in ("_rst_n", "_reset_n", "_rstn", "_reset"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return name.upper()

    def _get_node_size(self, node: Node) -> Tuple[int, int]:
        """根据节点类型返回 (width, height)"""
        if node.node_type.startswith("source"):
            return (200, 40)
        elif node.node_type == "reset_source":
            return (180, 32)
        elif node.node_type == "mux":
            return (100, 40)
        elif node.node_type == "rst_and":
            return (44, 52)
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
        text_color = self._get_text_color(node)
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
            "strokeColor": text_color,
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

    @staticmethod
    def _get_text_color(node: Node) -> str:
        if node.node_type == "source_input":
            return "#ffffff"
        if node.node_type == "reset_source":
            return "#166534"
        if node.node_type == "output":
            return "#075985"
        if node.node_type == "rst_and":
            return "#c2410c"
        return "#1e1e1e"

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
            text = node.attr if node.attr else "MUX"
        elif node.node_type == "rst_and":
            text = node.attr if node.attr else "&"
        elif node.node_type == "div":
            text = node.attr if node.attr else "DIV"
        elif node.node_type in ("icg", "icg_off"):
            text = node.attr if node.attr else "ICG"
        elif node.node_type == "occ":
            text = node.attr if node.attr else "OCC"
        elif node.node_type == "reg":
            text = node.attr if node.attr else "REG"
        elif node.node_type == "soft":
            text = "SOFT"
        elif node.node_type == "and":
            text = node.attr if node.attr else "&"
        elif node.node_type == "ctrl":
            text = node.attr if node.attr else ""
        else:
            text = node.name
        
        # NOTE 注释（如频率）标注到节点框内
        if node.note:
            text = f"{text}\n{node.note}"
        return text

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
