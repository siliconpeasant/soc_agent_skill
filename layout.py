"""
链路式列布局引擎

策略：
1. 固定列：Source(0) -> DIV(1) -> ICG(2) -> OCC(3) -> Output(4)
2. 按源时钟分组，每组占一块垂直区域
3. 组内按输出名称排序，均匀分布
4. 组间留大间距
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
        group_gap: float = 60,
    ):
        self.level_spacing = level_spacing
        self.node_spacing = node_spacing
        self.start_x = start_x
        self.start_y = start_y
        self.group_gap = group_gap

    def compute(self, graph: Graph):
        """计算所有节点坐标"""
        # 按源时钟分组
        groups = graph.get_source_groups()

        # 按源时钟名称排序组
        sorted_sources = sorted(groups.keys())

        current_y = self.start_y

        for src_name in sorted_sources:
            outputs = groups[src_name]
            outputs.sort()

            # 计算这组需要的垂直空间
            # 找到这组中所有节点（包括中间节点）
            group_nodes = self._collect_group_nodes(graph, src_name, outputs)

            # 按链路分组：每条链路（一个输出）的节点
            chains = {}
            for out in outputs:
                chain = self._get_chain_nodes(graph, src_name, out)
                chains[out] = chain

            # 计算链路的理想Y：以源节点为中心
            # 但源节点可能被多条链路共享，所以源节点的Y = 这组的中点
            num_chains = len(chains)
            total_height = (num_chains - 1) * self.node_spacing
            group_center_y = current_y + total_height / 2

            # 放置源节点
            if src_name in graph.nodes:
                graph.nodes[src_name].x = self.start_x
                graph.nodes[src_name].y = group_center_y

            # 放置每条链路的节点
            for i, out in enumerate(outputs):
                chain_y = current_y + i * self.node_spacing
                chain = chains[out]
                for node_name in chain:
                    if node_name in graph.nodes:
                        node = graph.nodes[node_name]
                        node.x = self.start_x + node.level * self.level_spacing
                        node.y = chain_y

            # 更新 current_y
            current_y += total_height + self.group_gap

        # 所有 output 节点对齐到最右列
        max_level = graph.get_max_level()
        for node in graph.nodes.values():
            if node.node_type == "output":
                node.x = self.start_x + max_level * self.level_spacing

        # 放置 AND 节点和 ctrl 节点
        self._place_and_nodes(graph)

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

    def _collect_group_nodes(self, graph: Graph, src_name: str, outputs: List[str]) -> List[str]:
        """收集一个源时钟组内的所有节点名称"""
        result = [src_name]
        for out in outputs:
            result.extend(self._get_chain_nodes(graph, src_name, out))
        return result

    def _get_chain_nodes(self, graph: Graph, src_name: str, output_name: str) -> List[str]:
        """获取从源到输出的链路上所有节点（不包括源）"""
        # 找到从 output 回溯到 src 的路径
        path = []
        current = output_name
        while current != src_name and current in graph.nodes:
            path.append(current)
            prev_nodes = [s for s, d in graph.edges if d == current]
            if not prev_nodes:
                break
            current = prev_nodes[0]
        path.reverse()
        return path
