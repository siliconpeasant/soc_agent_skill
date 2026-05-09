"""
主入口脚本
用法：
    python cr_tree_diag_gen/main.py
    python cr_tree_diag_gen/main.py <input.xlsx>          # 同时输出 .drawio + .excalidraw
    python cr_tree_diag_gen/main.py <input.xlsx> <output.drawio>
    python cr_tree_diag_gen/main.py <input.xlsx> <output.excalidraw>
"""
import sys
import os

# 确保能导入 scripts 包内模块（支持直接运行和模块运行）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.parser import CrgExcelParser
from scripts.graph import Graph
from scripts.layout import HierarchicalLayout
from scripts.renderer import DrawioRenderer
from scripts.excalidraw_renderer import ExcalidrawRenderer


def _derive_output_stem(input_path):
    input_stem = os.path.splitext(os.path.basename(input_path))[0]
    if input_stem.endswith("_table"):
        return input_stem[:-6] + "_tree"
    else:
        return input_stem + "_tree"


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) >= 2:
        input_path = sys.argv[1]
    else:
        input_path = os.path.join(script_dir, "input", "clock_table.xlsx")

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
        output_paths = [output_path]
    else:
        # 未指定输出路径：同时输出 drawio + excalidraw
        output_stem = _derive_output_stem(input_path)
        output_dir = os.path.join(PROJECT_ROOT, "examples", "output")
        output_paths = [
            os.path.join(output_dir, output_stem + ".drawio"),
            os.path.join(output_dir, output_stem + ".excalidraw"),
        ]

    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print("=" * 60)
    print("CRG Tree -> Draw.io / Excalidraw Generator")
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
    title = f"CRG {tree_type}"
    for output_path in output_paths:
        print(f"\n[4/4] Rendering to: {output_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        ext = os.path.splitext(output_path)[1].lower()
        if ext in (".excalidraw", ".json"):
            renderer = ExcalidrawRenderer()
            renderer.render(graph, output_path, title=title)
            print("  -> Excalidraw done!")
        else:
            renderer = DrawioRenderer()
            renderer.render(graph, output_path, title=title)
            print("  -> Draw.io done!")

    print("\n" + "=" * 60)
    if len(output_paths) > 1:
        print("All outputs generated!")
    print("=" * 60)


if __name__ == "__main__":
    main()
