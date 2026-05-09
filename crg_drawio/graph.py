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
        self._build_generic(rows, is_reset=False)

    def build_reset_tree_from_rows(self, rows: List[dict]):
        """从表格行构建复位树链路图"""
        self._build_generic(rows, is_reset=True)

    def _build_generic(self, rows: List[dict], is_reset: bool):
        """通用链路构建器（时钟树 / 复位树）"""
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

        # 收集所有信号
        signals = {}
        for idx, row in enumerate(rows):
            name = _s("NAME")
            if not name:
                continue
            skip_key = "Reset Generate" if is_reset else "Clock Generate"
            if skip_key in name:
                continue
            skip_names = ["NAME", "SEL", "SRC0", "SRC1", "MUX_DFLT", "DIV", "DIV_WIDTH", "DIV_DFLT",
                          "OCC/SCAN MUX", "ICG", "ICG_DFLT", "CE_DISEN", "ATTR",
                          "REG_NAME", "SOFT_LC", "SOFT_DFLT", "INOUT",
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
                "occ": _s("OCC/SCAN MUX"),
                "icg": _s("ICG"),
                "icg_dflt": _s("ICG_DFLT"),
                "reg_name": _s("REG_NAME"),
                "soft_lc": _s("SOFT_LC"),
                "soft_dflt": _s("SOFT_DFLT"),
                "order": idx,
            }

        # 创建所有信号节点
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
            ))

        # 为每个有 src0 的信号创建组件链路
        for name, info in signals.items():
            src0 = info["src0"]
            if not src0:
                continue
            
            prev = src0
            
            # MUX（如果 SRC1~SRC3 存在且为有效信号名）
            raw_srcs = [info["src1"], info["src2"], info["src3"]]
            # 复位树：过滤掉 "SOFT" 等非信号控制字
            ignore_list = ("SOFT", "") if is_reset else ("",)
            srcs = [s for s in raw_srcs if s and s.upper() not in ignore_list]
            has_mux = len(srcs) > 0
            if has_mux:
                mux_name = f"{name}_mux"
                self.add_node(Node(
                    name=mux_name,
                    node_type="mux",
                    attr="MUX",
                    source=src0,
                ))
                self.add_edge(src0, mux_name)
                for src in srcs:
                    if src not in self.nodes:
                        self.add_node(Node(name=src, node_type="source_internal", attr="internal", source=src))
                    self.add_edge(src, mux_name)
                prev = mux_name
            
            if is_reset:
                # 复位树链路：REG → SOFT → output
                if info["reg_name"]:
                    reg_name = f"{name}_reg"
                    self.add_node(Node(
                        name=reg_name,
                        node_type="reg",
                        attr=info["reg_name"],
                        source=src0,
                    ))
                    self.add_edge(prev, reg_name)
                    prev = reg_name
                
                if info["soft_lc"]:
                    soft_name = f"{name}_soft"
                    soft_label = info["soft_lc"]
                    if info["soft_dflt"]:
                        soft_label += f" ({info['soft_dflt']})"
                    self.add_node(Node(
                        name=soft_name,
                        node_type="soft",
                        attr=soft_label,
                        source=src0,
                    ))
                    self.add_edge(prev, soft_name)
                    prev = soft_name
            else:
                # 时钟树链路：DIV → OCC → ICG → output
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
            
            # 连接到目标节点
            self.add_edge(prev, name)
        
        # 计算 level
        self._compute_levels()
        
        # 调整 output 节点的 level，使其不与 na/internal 同列
        self._align_outputs()
        
        # 删除孤立的源节点（没有出边）
        self._remove_isolated_sources()
        
        # 为每个节点计算根源头
        self._compute_root_sources()

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
