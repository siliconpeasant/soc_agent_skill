"""
图模型 —— 动态拓扑

核心变化：
- 支持 MUX（SRC0 + SRC1）
- level 不固定，按链路组件数动态决定
- na/internal 是中间节点，不是 output
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict


@dataclass
class Node:
    """节点"""
    name: str           # 显示名称
    node_type: str      # source_input / source_internal / mux / div / icg / icg_off / occ / na / output
    attr: str = ""      # 附加信息
    source: str = ""    # 所属的根源头时钟
    order: int = 0      # 在原始表格中的顺序
    note: str = ""      # NOTE 注释（如频率）
    # 布局
    level: int = 0      # 列号（动态计算）
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
        """从表格行构建时钟树链路图"""
        signals = self._parse_signals(rows, is_reset=False)
        self._create_signal_nodes(signals, is_reset=False)
        self._build_clock_chain(signals)
        self._post_build()

    def build_reset_tree_from_rows(self, rows: List[dict]):
        """从表格行构建复位树链路图"""
        signals = self._parse_signals(rows, is_reset=True)
        self._create_signal_nodes(signals, is_reset=True)
        self._build_reset_chain(signals)
        self._post_build()

    def _post_build(self):
        """构建后的通用后处理"""
        self._compute_levels()
        self._align_outputs()
        self._remove_isolated_sources()
        self._compute_root_sources()

    def _parse_signals(self, rows: List[dict], is_reset: bool) -> dict:
        """解析表格行，收集所有信号信息"""
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

        signals = {}
        for idx, row in enumerate(rows):
            name = _s("NAME")
            if not name:
                continue
            skip_key = "Reset Generate" if is_reset else "Clock Generate"
            if skip_key in name:
                continue
            skip_names = ["NAME", "SRC0", "SRC1", "MUX_DFLT", "DIV", "DIV_WIDTH", "DIV_DFLT",
                          "OCC", "ICG", "ICG_DFLT", "ATTR",
                          "SOFT_DFLT",
                          "RESET GENERATE", "CLOCK GENERATE"]
            if name.upper() in skip_names:
                continue
                
            signals[name] = {
                "attr": _s("ATTR").lower(),
                "src0": _s("SRC0"),
                "src1": _s("SRC1"),
                "src2": _s("SRC2"),
                "src3": _s("SRC3"),
                "mux_dflt": _s("MUX_DFLT"),
                "div": _s("DIV"),
                "div_width": _s("DIV_WIDTH").replace(".0", ""),
                "div_dflt": _s("DIV_DFLT").replace(".0", ""),
                "occ": _s("OCC"),
                "icg": _s("ICG"),
                "icg_dflt": _s("ICG_DFLT"),
                "soft_dflt": _s("SOFT_DFLT"),
                "note": _s("NOTE"),
                "order": idx,
            }
        return signals

    def _create_signal_nodes(self, signals: dict, is_reset: bool = False):
        """为所有信号创建基础节点"""
        for name, info in signals.items():
            attr = info["attr"]
            if attr == "input":
                node_type = "source_input"
            elif attr == "internal":
                node_type = "source_internal"
            elif attr == "na":
                node_type = "na"
            elif attr == "output":
                node_type = "output"
            else:
                node_type = "source_internal"
            
            self.add_node(Node(
                name=name,
                node_type=node_type,
                attr=attr,
                order=info["order"],
                note=info.get("note", ""),
            ))

    def _add_mux_if_needed(self, name: str, info: dict, prev: str, is_reset: bool, mux_type: str = "mux") -> str:
        """如果需要，创建 MUX/AND 节点并返回新的 prev"""
        raw_srcs = [info["src1"], info["src2"], info["src3"]]
        ignore_list = ("SOFT", "") if is_reset else ("",)
        srcs = [s for s in raw_srcs if s and s.upper() not in ignore_list]
        if not srcs:
            return prev
        
        src0 = info["src0"]
        gate_name = f"{name}_{mux_type}"
        self.add_node(Node(
            name=gate_name,
            node_type=mux_type,
            attr="&" if mux_type == "rst_and" else "MUX",
            source=src0,
        ))
        self.add_edge(src0, gate_name)
        for src in srcs:
            if src not in self.nodes:
                self.add_node(Node(name=src, node_type="source_internal", attr="internal", source=src))
            elif not self.nodes[src].node_type.startswith("source"):
                # SRC2/SRC3 引用 output 节点时，创建 source_internal 副本放在 source 列
                src_alias = f"{src}_in"
                if src_alias not in self.nodes:
                    self.add_node(Node(name=src_alias, node_type="source_internal", attr="internal", source=src))
                src = src_alias
            self.add_edge(src, gate_name)
        return gate_name

    def _build_clock_chain(self, signals: dict):
        """时钟树链路：source → mux → div → occ → icg → output"""
        for name, info in signals.items():
            src0 = info["src0"]
            if not src0:
                continue
            
            prev = self._add_mux_if_needed(name, info, src0, is_reset=False, mux_type="mux")
            
            if info["div"]:
                div_name = f"{name}_div"
                div_label = "DIV"
                if info["div_dflt"]:
                    div_label += info["div_dflt"]
                elif info["div_width"]:
                    div_label += info["div_width"]
                self.add_node(Node(
                    name=div_name,
                    node_type="div",
                    attr=div_label,
                    source=src0,
                ))
                self.add_edge(prev, div_name)
                prev = div_name
            
            if info["occ"]:
                occ_name = f"{name}_occ"
                self.add_node(Node(
                    name=occ_name,
                    node_type="occ",
                    attr=info["occ"],
                    source=src0,
                ))
                self.add_edge(prev, occ_name)
                prev = occ_name
            
            if info["icg"].upper() == "Y":
                icg_name = f"{name}_icg"
                icg_type = "icg" if info.get("icg_dflt", "").upper() == "Y" else "icg_off"
                self.add_node(Node(
                    name=icg_name,
                    node_type=icg_type,
                    attr="ICG",
                    source=src0,
                ))
                self.add_edge(prev, icg_name)
                prev = icg_name
            
            self.add_edge(prev, name)

    def _build_reset_chain(self, signals: dict):
        """复位树链路：source → mux → soft → output（SOFT 节点颜色由 SOFT_DFLT 决定）"""
        for name, info in signals.items():
            src0 = info["src0"]
            if not src0:
                continue
            
            prev = self._add_mux_if_needed(name, info, src0, is_reset=True, mux_type="rst_and")
            
            # SOFT 节点：如果 SOFT_DFLT 有值（Y/N）则创建，颜色由 SOFT_DFLT 决定
            soft_dflt = info.get("soft_dflt", "")
            if soft_dflt:
                soft_name = f"{name}_soft"
                self.add_node(Node(
                    name=soft_name,
                    node_type="soft",
                    attr=soft_dflt,  # attr 存 Y/N，用于颜色区分
                    source=src0,
                ))
                self.add_edge(prev, soft_name)
                prev = soft_name
            
            self.add_edge(prev, name)

    def _compute_levels(self):
        """拓扑排序计算 level"""
        in_degree = {name: 0 for name in self.nodes}
        for src, dst in self.edges:
            if dst in in_degree:
                in_degree[dst] += 1
        
        from collections import deque
        queue = deque()
        for name, deg in in_degree.items():
            if deg == 0:
                self.nodes[name].level = 0
                queue.append(name)
        
        while queue:
            current = queue.popleft()
            current_level = self.nodes[current].level
            
            for src, dst in self.edges:
                if src == current:
                    new_level = current_level + 1
                    if new_level > self.nodes[dst].level:
                        self.nodes[dst].level = new_level
                    
                    in_degree[dst] -= 1
                    if in_degree[dst] == 0:
                        queue.append(dst)

    def _align_outputs(self):
        """将 output 节点对齐到不与 na/internal 同列的最右位置"""
        # 找到 na 和 internal 节点占用的 level
        occupied_levels = set()
        for node in self.nodes.values():
            if node.node_type in ("na", "source_internal"):
                occupied_levels.add(node.level)
        
        # 找到当前最大 level
        max_level = max((n.level for n in self.nodes.values()), default=0)
        
        # 为 output 找一个不冲突的位置
        output_level = max_level + 1
        while output_level in occupied_levels:
            output_level += 1
        
        for node in self.nodes.values():
            if node.node_type == "output":
                node.level = output_level

    def get_nodes_by_level(self) -> Dict[int, List[Node]]:
        result = defaultdict(list)
        for node in self.nodes.values():
            result[node.level].append(node)
        return dict(result)

    def get_max_level(self) -> int:
        return max((n.level for n in self.nodes.values()), default=0)

    def _remove_isolated_sources(self):
        """删除没有出边的孤立源节点，以及不属于任何 output 链路的孤立中间节点"""
        # 第一步：删除没有出边的孤立源节点
        to_remove = []
        for name, node in self.nodes.items():
            if node.node_type.startswith("source"):
                has_out = any(src == name for src, _ in self.edges)
                if not has_out:
                    to_remove.append(name)
        for name in to_remove:
            del self.nodes[name]
        
        # 第二步：从所有 output 节点回溯，标记可达节点
        from collections import deque
        reachable = set()
        outputs = [n.name for n in self.nodes.values() if n.node_type == "output"]
        queue = deque(outputs)
        for out in outputs:
            reachable.add(out)
        
        while queue:
            current = queue.popleft()
            # 找到指向 current 的所有源节点
            for src, dst in self.edges:
                if dst == current and src in self.nodes and src not in reachable:
                    reachable.add(src)
                    queue.append(src)
        
        # 删除不可达的节点（保留 source 节点，因为即使没有 output 引用，source 也应该显示）
        unreachable = [name for name in self.nodes if name not in reachable and not self.nodes[name].node_type.startswith("source")]
        for name in unreachable:
            del self.nodes[name]
        
        # 删除连接到已删除节点的边
        self.edges = [(src, dst) for src, dst in self.edges if src in self.nodes and dst in self.nodes]

    def _compute_root_sources(self):
        """为每个节点计算根源头（BFS 从源节点传播）"""
        from collections import deque
        queue = deque()
        
        # 初始化：源节点的 root_source 是自己
        for name, node in self.nodes.items():
            if node.node_type.startswith("source"):
                node.source = name
                queue.append(name)
        
        while queue:
            current = queue.popleft()
            current_root = self.nodes[current].source
            
            for src, dst in self.edges:
                if src == current and dst in self.nodes:
                    if not self.nodes[dst].source:
                        self.nodes[dst].source = current_root
                        queue.append(dst)
                    # 如果已经有 root_source，不覆盖（保持第一个到达的）

    def validate(self) -> List[str]:
        errors = []
        for src, dst in self.edges:
            if src not in self.nodes:
                errors.append(f"Edge references unknown source '{src}'")
            if dst not in self.nodes:
                errors.append(f"Edge references unknown target '{dst}'")
        return errors
