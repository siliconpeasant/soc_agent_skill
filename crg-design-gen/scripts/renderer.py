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


def _get_node_height(node_type: str, attr: str = "") -> float:
    style = get_node_style(node_type, attr)
    return float(style.get("height", 50))


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
        is_reset = getattr(graph, "tree_type", "") == "reset"
        mxGraphModel.set("grid", "0" if is_reset else "1")
        mxGraphModel.set("gridSize", "10")
        mxGraphModel.set("guides", "1")
        mxGraphModel.set("tooltips", "1")
        mxGraphModel.set("connect", "1")
        mxGraphModel.set("arrows", "1")
        mxGraphModel.set("fold", "1")
        mxGraphModel.set("page", "1")
        mxGraphModel.set("pageScale", "1")
        page_width, page_height = self._get_page_size(graph)
        mxGraphModel.set("pageWidth", str(page_width))
        mxGraphModel.set("pageHeight", str(page_height))
        mxGraphModel.set("math", "0")
        mxGraphModel.set("shadow", "0")
        mxGraphModel.set("allowArrows", "1")
        mxGraphModel.set("connectableEdges", "1")

        root = ET.SubElement(mxGraphModel, "root")

        self.cell_id = 0
        ET.SubElement(root, "mxCell", {"id": str(self.cell_id)})
        self.cell_id += 1
        ET.SubElement(root, "mxCell", {"id": str(self.cell_id), "parent": "0", "style": "allowArrows=1"})
        self.cell_id += 1
        parent_id = "1"

        if is_reset:
            self._add_reset_structure(root, graph, parent_id, page_width, page_height)

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
            if node.node_type.startswith("source")
        })
        source_index_map = {name: i for i, name in enumerate(source_names)}

        # 预先为门控节点（MUX / rst_and）的输入边分配 entry 点
        # MUX rotation=90：src0 接视觉右侧偏上 -> entryX=0.25, entryY=1
        #                  src1 接视觉右侧偏下 -> entryX=0.75, entryY=1
        # rst_and（矩形）：src0 接左侧偏上 -> entryY=0.25
        #                 src1+ 接左侧偏下 -> entryY=0.75
        gate_entry_map = {}  # (src, dst) -> (entry_x, entry_y)
        for dst_name, node in graph.nodes.items():
            if node.node_type not in ("mux", "rst_and"):
                continue
            inputs = [src for src, d in graph.edges if d == dst_name]
            for i, src in enumerate(inputs):
                if node.node_type == "mux":
                    ex = "0.25" if i == 0 else "0.75"
                    ey = "1"
                    gate_entry_map[(src, dst_name)] = (ex, ey)
                elif node.node_type == "rst_and":
                    if i == 0:
                        ey = "0.25"
                    else:
                        extra_count = max(len(inputs) - 1, 1)
                        if extra_count == 1:
                            ey = "0.75"
                        else:
                            ey_val = 0.58 + (i - 1) * (0.32 / (extra_count - 1))
                            ey = f"{ey_val:.2f}"
                    gate_entry_map[(src, dst_name)] = ("0", ey)

        # 按 root_source 分组收集 source 出边（用于总线布线）
        source_edges = {}
        for src, dst in graph.edges:
            if graph.nodes[src].node_type.startswith("source"):
                source_edges.setdefault(src, []).append((src, dst))

        # 渲染 Source 出边（强制水平出发，每个 source 独立车道错开）
        for src_name, edges in source_edges.items():
            src_node = graph.nodes[src_name]
            src_right = src_node.x + 200
            src_center_y = src_node.y + 40 / 2
            edge_color = get_edge_color(src_name, source_index_map)
            idx = source_index_map[src_name]
            # 每个 source 的垂直总线错开 10px，避免重叠
            bus_x = src_right + 5 + idx * 10

            for src, dst in edges:
                if src not in node_id_map or dst not in node_id_map:
                    continue
                # 水平到总线位置，再垂直转向目标
                waypoints = [(bus_x, src_center_y)]
                entry_info = gate_entry_map.get((src, dst))
                if entry_info:
                    ex, ey = entry_info
                    self._add_edge(root, node_id_map[src], node_id_map[dst], parent_id, waypoints, edge_color, entry_y=ey, entry_x=ex)
                else:
                    self._add_edge(root, node_id_map[src], node_id_map[dst], parent_id, waypoints, edge_color)

        # 渲染中间节点边（所有边根据源端 root_source 着色）
        for src, dst in graph.edges:
            if graph.nodes[src].node_type.startswith("source"):
                continue
            if src not in node_id_map or dst not in node_id_map:
                continue
            src_node = graph.nodes[src]
            dst_node = graph.nodes[dst]
            src_center_y = src_node.y + 40 / 2

            # 根据源端节点的 root_source 决定颜色
            if src_node.node_type == "reset_source":
                edge_color = "#22c55e"
            else:
                root_src = self._get_root_source(graph, src)
                edge_color = get_edge_color(root_src, source_index_map)

            # 强制水平线：从源节点右侧中心出发，水平走一段再转向目标
            src_w = _get_node_width(src_node.node_type, src_node.attr)
            mid_x = src_node.x + src_w + 30
            waypoints = [(mid_x, src_center_y)]

            entry_info = gate_entry_map.get((src, dst))
            if entry_info:
                ex, ey = entry_info
                self._add_edge(root, node_id_map[src], node_id_map[dst], parent_id, waypoints, edge_color, entry_y=ey, entry_x=ex)
            else:
                # MUX 出边：exitX=0.5, exitY=0 -> 视觉左侧正中
                ex_x = "0.5" if graph.nodes[src].node_type == "mux" else None
                ex_y = "0" if graph.nodes[src].node_type == "mux" else None
                self._add_edge(root, node_id_map[src], node_id_map[dst], parent_id, waypoints, edge_color, exit_x=ex_x, exit_y=ex_y)

        tree = ET.ElementTree(mxfile)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

        print(f"Saved: {output_path}")
        print(f"  Nodes: {len(graph.nodes)}")
        print(f"  Edges: {len(graph.edges)}")

    def _get_root_source(self, graph: Graph, node_name: str) -> str:
        """从节点追溯回根源头"""
        visited = set()
        current = node_name
        while current in graph.nodes:
            if current in visited:
                break
            visited.add(current)
            node = graph.nodes[current]
            if node.node_type.startswith("source"):
                return current
            prev = [src for src, dst in graph.edges if dst == current]
            if not prev:
                break
            current = prev[0]
        return current

    def _get_page_size(self, graph: Graph) -> tuple:
        if not graph.nodes:
            return (850, 1100)
        max_right = max(
            node.x + _get_node_width(node.node_type, node.attr)
            for node in graph.nodes.values()
        )
        max_bottom = max(
            node.y + _get_node_height(node.node_type, node.attr)
            for node in graph.nodes.values()
        )
        return (
            max(850, int(max_right + 120)),
            max(1100, int(max_bottom + 120)),
        )

    def _add_reset_structure(self, root, graph: Graph, parent_id: str, page_width: int, page_height: int):
        cols = self._get_reset_columns(graph)
        if not cols:
            return

        band_y = 92
        for label, x, width, _color in cols:
            self._add_small_label(root, parent_id, label, x, band_y - 24, width)

        self._add_reset_row_labels(root, graph, parent_id)

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

    def _add_background_band(self, root, parent_id: str, x: float, y: float, width: float, height: float, fill: str):
        cell = ET.SubElement(root, "mxCell")
        cell.set("id", str(self.cell_id))
        cell.set("value", "")
        cell.set("style", f"rounded=0;whiteSpace=wrap;html=1;fillColor={fill};strokeColor=none;opacity=55;")
        cell.set("vertex", "1")
        cell.set("parent", parent_id)
        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("x", str(int(x)))
        geo.set("y", str(int(y)))
        geo.set("width", str(int(width)))
        geo.set("height", str(int(height)))
        geo.set("as", "geometry")
        self.cell_id += 1

    def _add_small_label(self, root, parent_id: str, text: str, x: float, y: float, width: float):
        cell = ET.SubElement(root, "mxCell")
        cell.set("id", str(self.cell_id))
        cell.set("value", text)
        cell.set("style", "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=11;fontStyle=1;fontColor=#64748b;")
        cell.set("vertex", "1")
        cell.set("parent", parent_id)
        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("x", str(int(x)))
        geo.set("y", str(int(y)))
        geo.set("width", str(int(width)))
        geo.set("height", "20")
        geo.set("as", "geometry")
        self.cell_id += 1

    def _add_reset_row_labels(self, root, graph: Graph, parent_id: str):
        local_nodes = [n for n in graph.nodes.values() if n.node_type == "reset_source"]
        outputs = [n for n in graph.nodes.values() if n.node_type == "output"]
        if not (local_nodes and outputs):
            return

        label_x = min(n.x for n in local_nodes) - 82
        for output in sorted(outputs, key=lambda n: n.order):
            domain = self._reset_domain_label(output.name)
            cell = ET.SubElement(root, "mxCell")
            cell.set("id", str(self.cell_id))
            cell.set("value", domain)
            cell.set("style", "text;html=1;strokeColor=none;fillColor=none;align=right;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=10;fontStyle=1;fontColor=#94a3b8;")
            cell.set("vertex", "1")
            cell.set("parent", parent_id)
            geo = ET.SubElement(cell, "mxGeometry")
            geo.set("x", str(int(label_x)))
            geo.set("y", str(int(output.y + 10)))
            geo.set("width", "60")
            geo.set("height", "18")
            geo.set("as", "geometry")
            self.cell_id += 1

    @staticmethod
    def _reset_domain_label(name: str) -> str:
        for suffix in ("_rst_n", "_reset_n", "_rstn", "_reset"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return name.upper()

    def _add_title(self, root, title: str, graph: Graph, parent_id: str):
        sources = sum(1 for n in graph.nodes.values() if n.node_type.startswith("source"))
        reset_sources = sum(1 for n in graph.nodes.values() if n.node_type == "reset_source")
        outputs = sum(1 for n in graph.nodes.values() if n.node_type == "output")
        divs = sum(1 for n in graph.nodes.values() if n.node_type == "div")
        icgs = sum(1 for n in graph.nodes.values() if n.node_type in ("icg", "icg_off"))
        occs = sum(1 for n in graph.nodes.values() if n.node_type == "occ")
        ands = sum(1 for n in graph.nodes.values() if n.node_type == "rst_and")
        softs = sum(1 for n in graph.nodes.values() if n.node_type == "soft")

        if getattr(graph, "tree_type", "") == "reset":
            text = (
                f"{title}\n"
                f"{sources} root sources  |  {reset_sources} local sources  |  "
                f"{outputs} outputs  |  {ands} AND  |  {softs} SOFT"
            )
        else:
            text = f"{title}\n{sources} sources  |  {outputs} outputs  |  {divs} DIV  |  {icgs} ICG  |  {occs} OCC"

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
        if node.node_type == "mux":
            display = node.attr if node.attr else "MUX"
        elif node.node_type == "rst_and":
            display = node.attr if node.attr else "&"
        elif node.node_type == "div":
            display = node.attr if node.attr else "DIV"
        elif node.node_type in ("icg", "icg_off"):
            display = node.attr if node.attr else "ICG"
        elif node.node_type == "occ":
            display = node.attr if node.attr else "OCC"
        elif node.node_type == "reg":
            display = node.attr if node.attr else "REG"
        elif node.node_type == "soft":
            display = "SOFT"
        elif node.node_type == "and":
            display = node.attr if node.attr else "&"
        elif node.node_type == "ctrl":
            display = node.attr if node.attr else ""
        else:
            display = node.name
        
        # NOTE 注释（如频率）标注到节点框内
        if node.note:
            display = f"{display}\n{node.note}"

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

    def _add_edge(self, root, src_id: str, dst_id: str, parent_id: str, waypoints: List[Tuple[float, float]] = None, stroke_color: str = None, entry_y: str = None, entry_x: str = None, exit_x: str = None, exit_y: str = None):
        eid = str(self.cell_id)
        style = build_edge_style(stroke_color=stroke_color, entry_y=entry_y, entry_x=entry_x, exit_x=exit_x, exit_y=exit_y)

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
