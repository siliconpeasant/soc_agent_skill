"""
Draw.io XML 渲染器 —— 链路式图

边布线策略：
1. Source 出边：所有线从 Source 中心点出发，水平到总线点，垂直到目标 Y，水平到目标
2. 中间节点边：同一 Y 的节点间强制水平直线
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple
from .graph import Graph, Node
from .styles import get_node_style, build_style_string, build_edge_style, get_edge_color

def _get_node_width(node_type: str, attr: str = "") -> float:
    style = get_node_style(node_type, attr)
    return float(style.get("width", 200))


class DrawioRenderer:
    def __init__(self):
        self.cell_id = 0

    def render(self, graph: Graph, output_path: str, title: str = "Clock Tree"):
        mxfile = ET.Element("mxfile")
        mxfile.set("host", "app.diagrams.net")
        mxfile.set("modified", "2026-05-07T00:00:00.000Z")
        mxfile.set("agent", "CRG-Drawio-Generator")
        mxfile.set("version", "24.0.0")

        diagram = ET.SubElement(mxfile, "diagram")
        diagram.set("name", title)
        diagram.set("id", "crg-diagram")

        mxGraphModel = ET.SubElement(diagram, "mxGraphModel")
        mxGraphModel.set("dx", "3000")
        mxGraphModel.set("dy", "2000")
        mxGraphModel.set("grid", "1")
        mxGraphModel.set("gridSize", "10")
        mxGraphModel.set("guides", "1")
        mxGraphModel.set("tooltips", "1")
        mxGraphModel.set("connect", "1")
        mxGraphModel.set("arrows", "1")
        mxGraphModel.set("fold", "1")
        mxGraphModel.set("page", "1")
        mxGraphModel.set("pageScale", "1")
        mxGraphModel.set("pageWidth", "850")
        mxGraphModel.set("pageHeight", "1100")
        mxGraphModel.set("math", "0")
        mxGraphModel.set("shadow", "0")

        root = ET.SubElement(mxGraphModel, "root")

        self.cell_id = 0
        ET.SubElement(root, "mxCell", {"id": str(self.cell_id)})
        self.cell_id += 1
        ET.SubElement(root, "mxCell", {"id": str(self.cell_id), "parent": "0"})
        self.cell_id += 1
        parent_id = "1"

        # 标题
        self._add_title(root, title, graph, parent_id)

        # 过滤掉没有出边的孤立 Source 节点
        active_nodes = {
            name: node for name, node in graph.nodes.items()
            if node.node_type != "source" or any(src == name for src, _ in graph.edges)
        }

        # 节点
        node_id_map: Dict[str, str] = {}
        for name, node in active_nodes.items():
            nid = self._add_node(root, node, parent_id)
            node_id_map[name] = nid

        # 构建源头索引映射（用于边颜色分配）
        source_names = sorted({
            name for name, node in graph.nodes.items()
            if node.node_type == "source"
        })
        source_index_map = {name: i for i, name in enumerate(source_names)}

        # 按源分组收集 Source 出边
        source_edges = {}  # src_name -> [(src, dst), ...]
        for src, dst in graph.edges:
            if graph.nodes[src].node_type == "source":
                source_edges.setdefault(src, []).append((src, dst))

        # 渲染 Source 出边（带总线 waypoints，不同源头不同颜色）
        bus_offset = 30  # Source 右侧总线偏移
        for src_name, edges in source_edges.items():
            src_node = graph.nodes[src_name]
            src_right = src_node.x + 200
            src_center_y = src_node.y + 40 / 2  # 统一高度 40
            edge_color = get_edge_color(src_name, source_index_map)

            for src, dst in edges:
                if src not in node_id_map or dst not in node_id_map:
                    continue
                dst_node = graph.nodes[dst]
                dst_center_y = dst_node.y + 40 / 2  # 统一高度 40

                # 如果 Source 和目标在同一 Y，不需要 waypoint
                if abs(src_center_y - dst_center_y) < 2:
                    waypoints = None
                else:
                    # 总线 waypoint：从 Source 中心水平出发，垂直到目标 Y
                    waypoints = [(src_right + bus_offset, dst_center_y)]
                self._add_edge(root, node_id_map[src], node_id_map[dst], parent_id, waypoints, edge_color)

        # 渲染中间节点边（强制水平，颜色跟随源头）
        for src, dst in graph.edges:
            if graph.nodes[src].node_type == "source":
                continue
            if src not in node_id_map or dst not in node_id_map:
                continue
            src_node = graph.nodes[src]
            dst_node = graph.nodes[dst]
            src_center_y = src_node.y + 40 / 2  # 统一高度 40

            # 颜色跟随目标节点的 source 属性
            edge_color = get_edge_color(dst_node.source, source_index_map)

            # 如果同一 Y，添加中间 waypoint 强制水平线；否则垂直连到目标 Y
            if abs(src_node.y - dst_node.y) < 2:
                src_w = _get_node_width(src_node.node_type, src_node.attr)
                dst_w = _get_node_width(dst_node.node_type, dst_node.attr)
                mid_x = (src_node.x + src_w + dst_node.x) / 2
                waypoints = [(mid_x, src_center_y)]
            else:
                dst_center_y = dst_node.y + 40 / 2
                waypoints = [(dst_node.x, dst_center_y)]

            self._add_edge(root, node_id_map[src], node_id_map[dst], parent_id, waypoints, edge_color)

        tree = ET.ElementTree(mxfile)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        print(f"Saved: {output_path}")
        print(f"  Nodes: {len(graph.nodes)}")
        print(f"  Edges: {len(graph.edges)}")

    def _add_title(self, root, title: str, graph: Graph, parent_id: str):
        sources = sum(1 for n in graph.nodes.values() if n.node_type == "source")
        outputs = sum(1 for n in graph.nodes.values() if n.node_type == "output")
        divs = sum(1 for n in graph.nodes.values() if n.node_type == "div")
        icgs = sum(1 for n in graph.nodes.values() if n.node_type == "icg")
        occs = sum(1 for n in graph.nodes.values() if n.node_type == "occ")

        text = f"{title}\\n{sources} sources  |  {outputs} outputs  |  {divs} DIV  |  {icgs} ICG  |  {occs} OCC"

        cell = ET.SubElement(root, "mxCell")
        cell.set("id", str(self.cell_id))
        cell.set("value", text)
        cell.set("style", "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#2c3e50;")
        cell.set("vertex", "1")
        cell.set("parent", parent_id)

        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("x", "80")
        geo.set("y", "30")
        geo.set("width", "600")
        geo.set("height", "50")
        geo.set("as", "geometry")
        self.cell_id += 1

    def _add_node(self, root, node: Node, parent_id: str) -> str:
        nid = str(self.cell_id)
        style_dict = get_node_style(node.node_type, node.attr)

        # 显示文本
        if node.node_type == "div":
            display = node.attr if node.attr else "DIV"
        elif node.node_type in ("icg", "icg_off"):
            display = node.attr if node.attr else "ICG"
        elif node.node_type == "occ":
            display = node.attr if node.attr else "OCC"
        elif node.node_type == "and":
            display = node.attr if node.attr else "&"
        elif node.node_type == "ctrl":
            display = node.attr if node.attr else ""
        else:
            display = node.name

        style = build_style_string(style_dict)

        cell = ET.SubElement(root, "mxCell")
        cell.set("id", nid)
        cell.set("value", display)
        cell.set("style", style)
        cell.set("vertex", "1")
        cell.set("parent", parent_id)

        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("x", str(int(node.x)))
        geo.set("y", str(int(node.y)))
        geo.set("width", str(style_dict.get("width", 200)))
        geo.set("height", str(style_dict.get("height", 50)))
        geo.set("as", "geometry")

        self.cell_id += 1
        return nid

    def _add_edge(self, root, src_id: str, dst_id: str, parent_id: str, waypoints: List[Tuple[float, float]] = None, stroke_color: str = None):
        eid = str(self.cell_id)
        style = build_edge_style(stroke_color=stroke_color) if stroke_color else build_edge_style()

        cell = ET.SubElement(root, "mxCell")
        cell.set("id", eid)
        cell.set("value", "")
        cell.set("style", style)
        cell.set("edge", "1")
        cell.set("parent", parent_id)
        cell.set("source", src_id)
        cell.set("target", dst_id)

        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("relative", "1")
        geo.set("as", "geometry")

        if waypoints:
            arr = ET.SubElement(geo, "Array")
            arr.set("as", "points")
            for x, y in waypoints:
                pt = ET.SubElement(arr, "mxPoint")
                pt.set("x", str(int(x)))
                pt.set("y", str(int(y)))

        self.cell_id += 1
