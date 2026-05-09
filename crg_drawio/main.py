"""
主入口脚本
用法：
    python crg_drawio/main.py
    python crg_drawio/main.py <input.xlsx> [output.drawio|output.excalidraw]
"""
import sys
import os

# 确保能导入 crg_drawio 包内模块（支持直接运行和模块运行）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from crg_drawio.parser import CrgExcelParser
from crg_drawio.graph import Graph
from crg_drawio.layout import HierarchicalLayout
from crg_drawio.renderer import DrawioRenderer
from crg_drawio.excalidraw_renderer import ExcalidrawRenderer


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) >= 2:
        input_path = sys.argv[1]
    else:
        input_path = os.path.join(script_dir, "input", "clock_table.xlsx")

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        # 根据输入文件名自动推导输出文件名
        input_stem = os.path.splitext(os.path.basename(input_path))[0]
        # 将 _table 后缀替换为 _tree
        if input_stem.endswith("_table"):
            output_stem = input_stem[:-6] + "_tree"
        else:
            output_stem = input_stem + "_tree"
        output_path = os.path.join(script_dir, "output", output_stem + ".drawio")

    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print("=" * 60)
    print("CRG Tree -> Draw.io Generator")
    print("=" * 60)

    # 1. 解析表格
    print(f"\n[1/4] Parsing: {input_path}")
    parser = CrgExcelParser(input_path)
    rows = parser.parse()
    summary = parser.get_summary(rows)
    print(f"  Total signals: {summary['total']}")
    print(f"  Attributes: {summary['attrs']}")

    # 检测表格类型（复位树 vs 时钟树）
    is_reset = any("SOFT_DFLT" in str(k).upper() for k in rows[0].keys()) if rows else False
    tree_type = "Reset Tree" if is_reset else "Clock Tree"

    # 2. 构建图
    print("\n[2/4] Building graph...")
    graph = Graph()
    if is_reset:
        graph.build_reset_tree_from_rows(rows)
    else:
        graph.build_from_rows(rows)
    errors = graph.validate()
    if errors:
        print("  Warnings:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  Validation passed")

    # 3. 布局
    print("\n[3/4] Computing layout...")
    layout = HierarchicalLayout(
        level_spacing=280,
        node_spacing=70,
        start_x=80,
        start_y=120,
    )
    layout.compute(graph)
    print(f"  Layout computed")

    # 4. 渲染
    print(f"\n[4/4] Rendering to: {output_path}")
    ext = os.path.splitext(output_path)[1].lower()
    title = f"CRG {tree_type}"
    if ext in (".excalidraw", ".json"):
        renderer = ExcalidrawRenderer()
        renderer.render(graph, output_path, title=title)
        print("\n" + "=" * 60)
        print("Done! Open https://excalidraw.com and drag the file in")
        print("=" * 60)
    else:
        renderer = DrawioRenderer()
        renderer.render(graph, output_path, title=title)
        print("\n" + "=" * 60)
        print("Done! Open the file with https://app.diagrams.net")
        print("=" * 60)


if __name__ == "__main__":
    main()
