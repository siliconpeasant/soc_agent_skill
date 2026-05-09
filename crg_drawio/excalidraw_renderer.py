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


def _get_node_colors(node_type: str) -> Dict[str, str]:
    return NODE_COLORS.get(node_type, NODE_COLORS["output"])


class ExcalidrawRenderer:
    def __init__(self):
        self.elements: List[Dict] = []

    def render(self, graph: Graph, output_path: str, title: str = "CRG Clock Tree"):
        self.elements = []

        # 1. 标题
        self._add_title(title, graph)

        # 2. 节点 → rectangle + text
        node_id_map: Dict[str, str] = {}
        for name, node in graph.nodes.items():
            eid = self._add_node(node)
            node_id_map[name] = eid

        # 3. 构建源头索引映射（用于边颜色分配）
        source_names = sorted({
            n.name for n in graph.nodes.values()
            if n.node_type.startswith("source")
        })
        source_index_map = {name: i for i, name in enumerate(source_names)}

        # 4. 边 → arrow
        for src, dst in graph.edges:
            if src not in node_id_map or dst not in node_id_map:
                continue
            src_node = graph.nodes[src]
            dst_node = graph.nodes[dst]
            root_src = self._get_root_source(graph, src)
            stroke = EDGE_COLORS[source_index_map.get(root_src, 0) % len(EDGE_COLORS)]
            self._add_arrow(node_id_map[src], node_id_map[dst], src_node, dst_node, stroke)

        # 5. 写入文件
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
        print(f"  Nodes: {len(graph.nodes)}")
        print(f"  Edges: {len(graph.edges)}")

    def _add_title(self, title: str, graph: Graph):
        sources = sum(1 for n in graph.nodes.values() if n.node_type.startswith("source"))
        outputs = sum(1 for n in graph.nodes.values() if n.node_type == "output")
        divs = sum(1 for n in graph.nodes.values() if n.node_type == "div")
        icgs = sum(1 for n in graph.nodes.values() if n.node_type in ("icg", "icg_off"))
        occs = sum(1 for n in graph.nodes.values() if n.node_type == "occ")
        text = f"{title}\n{sources} sources  |  {outputs} outputs  |  {divs} DIV  |  {icgs} ICG  |  {occs} OCC"

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

    def _add_node(self, node: Node) -> str:
        eid = _uid()
        colors = _get_node_colors(node.node_type)
        w = 180 if node.node_type.startswith("source") else 140
        h = 45

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
            "fontSize": 14,
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

    def _add_arrow(self, src_eid: str, dst_eid: str, src_node: Node, dst_node: Node, stroke_color: str):
        # 起点：源节点右侧中心（手动计算，不用 binding）
        src_w = 180 if src_node.node_type.startswith("source") else 140
        start_x = src_node.x + src_w
        start_y = src_node.y + 45 / 2

        # 终点：目标节点左侧中心
        end_x = dst_node.x
        end_y = dst_node.y + 45 / 2

        dx = end_x - start_x
        dy = end_y - start_y

        # 正交布线：先垂直，再水平（└─ 形状）
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
            "startArrowhead": None,
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
        elif node.node_type == "div":
            return node.attr if node.attr else "DIV"
        elif node.node_type in ("icg", "icg_off"):
            return node.attr if node.attr else "ICG"
        elif node.node_type == "occ":
            return node.attr if node.attr else "OCC"
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
