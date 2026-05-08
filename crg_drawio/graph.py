"""
图模型 —— 链路式拓扑

核心变化：
- DIV / ICG / OCC 不再是属性，而是独立的中间节点
- 每个子时钟形成一条链路：SRC -> [DIV] -> [ICG] -> [OCC] -> OUTPUT
- 所有节点严格对齐到列
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict


@dataclass
class Node:
    """节点"""
    name: str           # 显示名称
    node_type: str      # source / div / icg / occ / output
    attr: str = ""      # 原始 ATTR（仅 source/output 有效）
    source: str = ""    # 所属的根源头时钟
    # 布局
    level: int = 0      # 列号 0~4
    x: float = 0.0
    y: float = 0.0


class Graph:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[tuple] = []   # (source_id, target_id)

    def add_node(self, node: Node) -> Node:
        self.nodes[node.name] = node
        return node

    def add_edge(self, src: str, dst: str):
        self.edges.append((src, dst))

    def build_from_rows(self, rows: List[dict]):
        """从表格行构建链路图"""
        def _s(key, default=""):
            v = row.get(key, default)
            if v is None:
                return default
            if isinstance(v, float):
                import math
                if math.isnan(v):
                    return default
            s = str(v).strip()
            if s in ("nan", "NaN", "<NA>", "None"):
                return default
            return s

        # 第一步：收集所有源时钟和目标时钟
        sources = set()
        targets = []
        for row in rows:
            name = _s("NAME")
            attr = _s("ATTR").lower()
            src0 = _s("SRC0")
            if not name:
                continue
            if attr in ("input", "internal") and not src0:
                # 纯源时钟
                sources.add(name)
            if src0:
                targets.append({
                    "name": name,
                    "attr": attr,
                    "src0": src0,
                    "div": _s("DIV"),
                    "div_width": _s("DIV_WIDTH").replace(".0", ""),
                    "div_dflt": _s("DIV_DFLT").replace(".0", ""),
                    "occ": _s("OCC/SCAN MUX"),
                    "icg": _s("ICG"),
                    "icg_dflt": _s("ICG_DFLT"),
                    "icg_external": _s("ICG_external"),
                    # "icg_internal": _s("ICG_internal"),
                })

        # 第二步：创建源节点
        for src_name in sources:
            # 查找源节点的 ATTR
            src_attr = "internal"
            for row in rows:
                if _s("NAME") == src_name:
                    src_attr = _s("ATTR").lower() or "internal"
                    break
            self.add_node(Node(
                name=src_name,
                node_type="source",
                attr=src_attr,
                level=0,
            ))

        # 第三步：为每个目标时钟创建链路
        for t in targets:
            src_name = t["src0"]
            out_name = t["name"]

            # 确保源节点存在（如果不存在，自动创建）
            if src_name not in self.nodes:
                self.add_node(Node(
                    name=src_name,
                    node_type="source",
                    attr="internal",
                    source=src_name,
                    level=0,
                ))

            # 固定列：source(0) -> div(1) -> icg(2) -> occ(3) -> output(4)
            prev = src_name

            # DIV 节点（列1）
            if t["div"]:
                div_name = f"{out_name}_div"
                # 参考图格式：DIV + 分频比
                div_label = "DIV"
                if t["div_dflt"]:
                    div_label += t["div_dflt"]
                elif t["div_width"]:
                    div_label += t["div_width"]
                self.add_node(Node(
                    name=div_name,
                    node_type="div",
                    attr=div_label,
                    source=src_name,
                    level=1,
                ))
                self.add_edge(prev, div_name)
                prev = div_name

            # ICG 节点（列2）
            if t["icg"].upper() == "Y":
                icg_name = f"{out_name}_icg"
                # ICG_DFLT=Y 时绿色，否则灰色
                icg_type = "icg" if t.get("icg_dflt", "").upper() == "Y" else "icg_off"
                self.add_node(Node(
                    name=icg_name,
                    node_type=icg_type,
                    attr="ICG",
                    source=src_name,
                    level=2,
                ))

                # 如果有 ICG_internal，插入 AND 节点：prev -> AND -> ICG，ctrl -> AND
                # if t.get("icg_internal"):
                #     and_name = f"{out_name}_and"
                #     ctrl_name = f"{out_name}_ctrl"
                #     self.add_node(Node(
                #         name=and_name,
                #         node_type="and",
                #         attr="&",
                #         level=2,
                #     ))
                #     self.add_node(Node(
                #         name=ctrl_name,
                #         node_type="ctrl",
                #         attr=t["icg_internal"],
                #         level=2,
                #     ))
                #     self.add_edge(prev, and_name)
                #     self.add_edge(ctrl_name, and_name)
                #     self.add_edge(and_name, icg_name)
                # else:
                self.add_edge(prev, icg_name)
                prev = icg_name

            # OCC 节点（列3）
            if t["occ"]:
                occ_name = f"{out_name}_occ"
                self.add_node(Node(
                    name=occ_name,
                    node_type="occ",
                    attr=t["occ"],
                    source=src_name,
                    level=3,
                ))
                self.add_edge(prev, occ_name)
                prev = occ_name

            # 输出节点（列4）
            self.add_node(Node(
                name=out_name,
                node_type="output",
                attr=t["attr"],
                level=4,
            ))
            self.add_edge(prev, out_name)

    def get_nodes_by_level(self) -> Dict[int, List[Node]]:
        result = defaultdict(list)
        for node in self.nodes.values():
            result[node.level].append(node)
        return dict(result)

    def get_max_level(self) -> int:
        return max((n.level for n in self.nodes.values()), default=0)

    def get_source_groups(self) -> Dict[str, List[str]]:
        """按源时钟分组，返回 {src_name: [target_name, ...]}"""
        groups = defaultdict(list)
        for src, dst in self.edges:
            src_node = self.nodes[src]
            if src_node.node_type == "source":
                # 找到这条链路的最终输出节点
                final = self._get_chain_output(dst)
                if final and final not in groups[src]:
                    groups[src].append(final)
            else:
                # 找到这个中间节点的源
                root_src = self._get_chain_source(src)
                if root_src:
                    final = self._get_chain_output(dst)
                    if final and final not in groups[root_src]:
                        groups[root_src].append(final)
        return dict(groups)

    def _get_chain_output(self, node_name: str) -> Optional[str]:
        """从中间节点追溯到最终输出"""
        visited = set()
        current = node_name
        while current in self.nodes:
            if current in visited:
                break
            visited.add(current)
            if self.nodes[current].node_type == "output":
                return current
            # 找到出边
            next_nodes = [dst for src, dst in self.edges if src == current]
            if not next_nodes:
                break
            current = next_nodes[0]
        return None

    def _get_chain_source(self, node_name: str) -> Optional[str]:
        """从中间节点追溯到源"""
        visited = set()
        current = node_name
        while current in self.nodes:
            if current in visited:
                break
            visited.add(current)
            if self.nodes[current].node_type == "source":
                return current
            prev_nodes = [src for src, dst in self.edges if dst == current]
            if not prev_nodes:
                break
            current = prev_nodes[0]
        return None

    def validate(self) -> List[str]:
        errors = []
        # 检查悬空边
        for src, dst in self.edges:
            if src not in self.nodes:
                errors.append(f"Edge references unknown source '{src}'")
            if dst not in self.nodes:
                errors.append(f"Edge references unknown target '{dst}'")
        return errors
