"""
节点样式配置 —— 动态链路图
"""

NODE_STYLES = {
    "source_input": {
        "shape": "rounded=1",
        "fillColor": "#27ae60",
        "strokeColor": "#1e8449",
        "fontColor": "#ffffff",
        "width": 200,
        "height": 40,
    },
    "source_internal": {
        "shape": "rounded=1",
        "fillColor": "#7f8c8d",
        "strokeColor": "#616a6b",
        "fontColor": "#ffffff",
        "width": 200,
        "height": 40,
    },
    "na": {
        "shape": "rounded=1",
        "fillColor": "#f39c12",
        "strokeColor": "#d35400",
        "fontColor": "#ffffff",
        "width": 220,
        "height": 40,
    },
    "output": {
        "shape": "rounded=1",
        "fillColor": "#aed6f1",
        "strokeColor": "#5dade2",
        "fontColor": "#1a5276",
        "width": 220,
        "height": 40,
    },
    "mux": {
        "shape": "mxgraph.basic.trapezoid",
        "fillColor": "#e8daef",
        "strokeColor": "#9b59b6",
        "fontColor": "#8e44ad",
        "width": 100,
        "height": 40,
        "rotation": 90,
    },
    "rst_and": {
        "shape": "rectangle",
        "fillColor": "#fff3bf",
        "strokeColor": "#f08c00",
        "fontColor": "#d9480f",
        "width": 40,
        "height": 60,
    },
    "reg": {
        "shape": "rectangle",
        "fillColor": "#d6eaf8",
        "strokeColor": "#3498db",
        "fontColor": "#2874a6",
        "width": 120,
        "height": 40,
    },
    "soft": {
        "shape": "rectangle",
        "fillColor": "#fdebd0",
        "strokeColor": "#e67e22",
        "fontColor": "#d35400",
        "width": 100,
        "height": 40,
    },
    "div": {
        "shape": "rectangle",
        "fillColor": "#ffffff",
        "strokeColor": "#333333",
        "fontColor": "#333333",
        "width": 100,
        "height": 40,
    },
    "icg": {
        "shape": "rectangle",
        "fillColor": "#d5f5e3",
        "strokeColor": "#27ae60",
        "fontColor": "#1e8449",
        "width": 80,
        "height": 40,
    },
    "icg_off": {
        "shape": "rectangle",
        "fillColor": "#e5e7e9",
        "strokeColor": "#7f8c8d",
        "fontColor": "#555555",
        "width": 80,
        "height": 40,
    },
    "and": {
        "shape": "rectangle",
        "fillColor": "#f1c40f",
        "strokeColor": "#d4ac0d",
        "fontColor": "#7f6000",
        "width": 40,
        "height": 40,
    },
    "ctrl": {
        "shape": "text",
        "fillColor": "none",
        "strokeColor": "none",
        "fontColor": "#333333",
        "width": 120,
        "height": 40,
    },
    "occ": {
        "shape": "rectangle",
        "fillColor": "#f5eef8",
        "strokeColor": "#9b59b6",
        "fontColor": "#8e44ad",
        "width": 80,
        "height": 40,
    },
}


def get_node_style(node_type: str, attr: str = "") -> dict:
    key = node_type
    if node_type == "source":
        key = f"source_{attr}" if f"source_{attr}" in NODE_STYLES else "source_input"
    elif node_type == "soft" and attr:
        # 复位树 SOFT 节点颜色：Y=绿色, N=灰色
        if attr.upper() == "Y":
            return {
                "shape": "rectangle",
                "fillColor": "#d5f5e3",
                "strokeColor": "#27ae60",
                "fontColor": "#1e8449",
                "width": 100,
                "height": 40,
            }
        elif attr.upper() == "N":
            return {
                "shape": "rectangle",
                "fillColor": "#e5e7e9",
                "strokeColor": "#7f8c8d",
                "fontColor": "#555555",
                "width": 100,
                "height": 40,
            }
    return NODE_STYLES.get(key, NODE_STYLES["output"]).copy()


def build_style_string(style_dict: dict) -> str:
    raw_shape = style_dict.get("shape", "rounded=1")
    # mxGraph 内置形状（rounded/rectangle/ellipse 等）可省略 shape= 前缀
    # 但 mxgraph.* 形状必须显式加 shape= 前缀
    if raw_shape.startswith("mxgraph."):
        shape_part = f"shape={raw_shape}"
    else:
        shape_part = raw_shape
    parts = [
        shape_part,
        "whiteSpace=wrap",
        "html=1",
        f"rotation={style_dict.get('rotation', 0)}",
        f"fillColor={style_dict.get('fillColor', '#95a5a6')}",
        f"strokeColor={style_dict.get('strokeColor', '#666666')}",
        f"strokeWidth={style_dict.get('strokeWidth', 2)}",
        f"fontColor={style_dict.get('fontColor', '#ffffff')}",
        "fontSize=11",
        "fontStyle=1",
    ]
    return ";".join(parts)


# 不同源头的边颜色调色板
EDGE_COLORS = [
    "#e74c3c",  # 红
    "#3498db",  # 蓝
    "#2ecc71",  # 绿
    "#f39c12",  # 橙
    "#9b59b6",  # 紫
    "#1abc9c",  # 青
    "#e91e63",  # 粉
    "#ff5722",  # 深橙
    "#00bcd4",  #  cyan
    "#8bc34a",  # 浅绿
    "#ff9800",  # 琥珀
    "#795548",  # 棕
]


def build_edge_style(exit_x: str = "1", exit_y: str = "0.5", entry_x: str = "0", entry_y: str = "0.5", stroke_color: str = "#555555") -> str:
    style = (
        "edgeStyle=orthogonalEdgeStyle;"
        "rounded=1;"
        "orthogonalLoop=1;"
        "html=1;"
        "strokeWidth=2;"
        f"strokeColor={stroke_color};"
        "jumpStyle=arc;"
        "jumpSize=10;"
    )
    if exit_x is not None:
        style += f"exitX={exit_x};"
    if exit_y is not None:
        style += f"exitY={exit_y};"
    if entry_x is not None:
        style += f"entryX={entry_x};"
    if entry_y is not None:
        style += f"entryY={entry_y};"
    return style


def get_edge_color(source_name: str, source_index_map: dict) -> str:
    """根据源头名称获取边颜色"""
    idx = source_index_map.get(source_name, 0)
    return EDGE_COLORS[idx % len(EDGE_COLORS)]
