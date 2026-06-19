"""
链路式列布局引擎

策略：
1. level 由拓扑排序动态决定
2. 按目标节点（output + na）的原始表格顺序排列 Y 坐标
3. 每条链路独立成行
4. 同一 level 的多个节点垂直错开，避免重叠
"""
from typing import Dict, List
from collections import defaultdict
from .graph import Graph, Node


class HierarchicalLayout:
    def __init__(
        self,
        level_spacing: float = 280,
        node_spacing: float = 70,
        start_x: float = 80,
        start_y: float = 120,
    ):
        self.level_spacing = level_spacing
        self.node_spacing = node_spacing
        self.start_x = start_x
        self.start_y = start_y

    def compute(self, graph: Graph):
        """计算所有节点坐标——按目标节点顺序排列"""
        if getattr(graph, "tree_type", "") == "reset":
            self._compute_reset_layout(graph)
            return

        # 收集所有目标节点（output + na），按原始表格 order 排序
        target_nodes = [n for n in graph.nodes.values()
                        if n.node_type in ("output", "na")]
        target_nodes.sort(key=lambda n: n.order)

        current_y = self.start_y

        for target in target_nodes:
            target_name = target.name

            # 获取这条链路上的所有节点（从目标回溯到根）
            chain = self._get_chain_nodes(graph, target_name)

            # 放置链路上的节点（已放置的节点不覆盖 Y）
            # 同一 level 的多个节点垂直错开，避免重叠
            level_offsets = {}
            for node_name in chain:
                if node_name in graph.nodes:
                    node = graph.nodes[node_name]
                    node.x = self.start_x + node.level * self.level_spacing
                    if node.y == 0:  # 首次放置
                        offset = level_offsets.get(node.level, 0)
                        node.y = current_y + offset * 60
                        level_offsets[node.level] = offset + 1

            current_y += self.node_spacing

        # 放置 AND 节点和 ctrl 节点
        self._place_and_nodes(graph)

        # 放置 rst_and 的外部输入 source_internal 节点
        self._place_rst_and_inputs(graph)

    def _compute_reset_layout(self, graph: Graph):
        """Reset tree layout: one output per row, local reset sources near its gate."""
        outputs = [n for n in graph.nodes.values() if n.node_type == "output"]
        outputs.sort(key=lambda n: n.order)
        if not outputs:
            return

        max_local_inputs = self._get_max_reset_local_inputs(graph)
        row_spacing = max(
            self.node_spacing,
            110 if max_local_inputs <= 2 else 130 + (max_local_inputs - 3) * 40,
        )
        root_x = self.start_x
        local_source_x = self.start_x + 300
        gate_x = self.start_x + 560
        soft_x = self.start_x + 660
        output_x = self.start_x + 800

        first_y = self.start_y
        last_y = self.start_y + (len(outputs) - 1) * row_spacing
        center_y = (first_y + last_y) / 2

        root_sources = [
            n for n in graph.nodes.values()
            if n.node_type.startswith("source")
        ]
        root_sources.sort(key=lambda n: n.order)
        root_stack_top = center_y - (len(root_sources) - 1) * 28 - 20
        for idx, node in enumerate(root_sources):
            node.x = root_x
            node.y = root_stack_top + idx * 56

        for row_idx, output in enumerate(outputs):
            row_y = self.start_y + row_idx * row_spacing
            output.x = output_x
            output.y = row_y

            prevs = [src for src, dst in graph.edges if dst == output.name]
            gate = None
            soft = None

            for prev in prevs:
                prev_node = graph.nodes.get(prev)
                if not prev_node:
                    continue
                if prev_node.node_type == "soft":
                    soft = prev_node
                    soft.x = soft_x
                    soft.y = row_y
                    soft_prevs = [src for src, dst in graph.edges if dst == soft.name]
                    gate = next(
                        (graph.nodes[src] for src in soft_prevs
                         if src in graph.nodes and graph.nodes[src].node_type == "rst_and"),
                        None,
                    )
                    output.x = output_x + 120
                elif prev_node.node_type == "rst_and":
                    gate = prev_node
                elif prev_node.node_type.startswith("source"):
                    # Direct reset: keep it compact even without an AND node.
                    output.x = gate_x

            if gate:
                gate.x = gate_x
                gate.y = row_y - 10
                self._place_reset_local_sources(graph, gate, local_source_x, row_y)

    def _place_reset_local_sources(self, graph: Graph, gate: Node, x: float, row_y: float):
        inputs = [src for src, dst in graph.edges if dst == gate.name]
        local_inputs = [
            src for src in inputs
            if src in graph.nodes and graph.nodes[src].node_type == "reset_source"
        ]
        count = len(local_inputs)
        if count == 0:
            return

        if count == 1:
            centers = [row_y + 35]
        elif count == 2:
            centers = [row_y + 35, row_y + 79]
        else:
            start = row_y + 30
            step = 36
            centers = [start + i * step for i in range(count)]

        for src, center in zip(local_inputs, centers):
            node = graph.nodes[src]
            node.x = x
            node.y = center - 17

    def _get_max_reset_local_inputs(self, graph: Graph) -> int:
        max_inputs = 0
        for node in graph.nodes.values():
            if node.node_type != "rst_and":
                continue
            local_count = sum(
                1 for src, dst in graph.edges
                if dst == node.name
                and src in graph.nodes
                and graph.nodes[src].node_type == "reset_source"
            )
            max_inputs = max(max_inputs, local_count)
        return max_inputs

    def _place_rst_and_inputs(self, graph: Graph):
        """rst_and 的外部输入 source_internal 节点放在 source 列，Y 坐标与 entryY=0.75 对齐"""
        for name, node in graph.nodes.items():
            if node.node_type != "rst_and":
                continue
            inputs = [src for src, dst in graph.edges if dst == name]
            for i, src in enumerate(inputs):
                if src not in graph.nodes:
                    continue
                src_node = graph.nodes[src]
                if src_node.node_type == "source_internal" and src_node.y == 0:
                    src_node.x = self.start_x
                    # 与 rst_and 的 entryY=0.75 对齐（高度 60，3/4 处 = y + 45）
                    # source_internal 高度=40，中心在 y + 20
                    src_node.y = node.y + 45 - 20

    def _place_and_nodes(self, graph: Graph):
        """AND 节点放在对应 ICG 的左侧，ctrl 在 AND 左侧"""
        for name, node in graph.nodes.items():
            if node.node_type == "and":
                # 找到 AND 节点连接的 ICG
                for src, dst in graph.edges:
                    if src == name and graph.nodes[dst].node_type in ("icg", "icg_off"):
                        icg_node = graph.nodes[dst]
                        node.x = icg_node.x - 80   # AND 在 ICG 左侧
                        node.y = icg_node.y        # 同 Y
                        break
            elif node.node_type == "ctrl":
                # 找到 ctrl 节点连接的 AND
                for src, dst in graph.edges:
                    if src == name and graph.nodes[dst].node_type == "and":
                        and_node = graph.nodes[dst]
                        node.x = and_node.x - 140  # ctrl 在 AND 左侧，留 20px 间隙
                        node.y = and_node.y        # 同 Y
                        break

    def _get_chain_nodes(self, graph: Graph, target_name: str) -> List[str]:
        """获取从目标节点回溯到根源的链路上所有节点（包含 MUX 的所有输入）"""
        path = []
        visited = set()

        def collect(node_name):
            if node_name not in graph.nodes or node_name in visited:
                return
            visited.add(node_name)
            path.append(node_name)

            prev_nodes = [src for src, dst in graph.edges if dst == node_name]
            if not prev_nodes:
                return

            if graph.nodes[node_name].node_type == "mux":
                # MUX 节点：收集所有输入（反转顺序，让 SRC0 在上面）
                for prev in reversed(prev_nodes):
                    collect(prev)
            else:
                # 普通节点：取 level 最小的前驱
                prev = min(prev_nodes, key=lambda n: graph.nodes[n].level if n in graph.nodes else 999)
                collect(prev)

        collect(target_name)
        path.reverse()
        return path
