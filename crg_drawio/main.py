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


def create_sample_xlsx(path: str):
    """基于用户截图创建示例 xlsx"""
    try:
        import openpyxl
    except ImportError:
        print("openpyxl not installed")
        sys.exit(1)

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "ClockTree"

    headers = [
        "NAME", "SEL", "SRC0", "SRC1", "MUX_DFLT", "DIV",
        "DIV_WIDTH", "DIV_DFLT", "OCC/SCAN MUX", "ICG",
        "ICG_DFLT", "ICG_external", "ICG_internal", "CE_DISEN", "ATTR"
    ]
    ws.append(headers)

    rows = [
        ["test_mode", "", "", "", "", "", "", "", "", "", "", "", "", "", "input"],
        ["cs_pll_clk", "", "", "", "", "", "", "", "", "", "", "", "", "", "input"],
        ["ao_misc_apb_clk", "", "", "", "", "", "", "", "", "", "", "", "", "", "input"],
        ["pad_ref_clk", "", "", "", "", "", "", "", "", "", "", "", "", "", "input"],
        ["secencdivclk", "", "", "", "", "", "", "", "", "", "", "", "", "", "input"],
        ["clk_gen_rst_n", "", "", "", "", "", "", "", "", "", "", "", "", "", "internal"],
        ["Clock Generate", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["ao_sc_apb_clk", "", "ao_misc_apb_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["pmu_apb_clk", "", "ao_misc_apb_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["pmu_ao_pclk", "", "ao_misc_apb_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["ao_crg_apb_clk", "", "ao_misc_apb_clk", "", "", "", "", "", "", "", "", "", "", "", "output"],
        ["ao_io_apb_clk", "", "ao_misc_apb_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["ao_vol_clk", "", "pad_ref_clk", "", "", "clk_divider", "8", "8", "OCC", "Y", "Y", "", "", "", "output"],
        ["ao_vol_pclk", "", "ao_misc_apb_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["ao_pll_monitor_clk", "", "ao_misc_apb_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["efuse_ctrl_ref_clk", "", "pad_ref_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["efuse_ctrl_apb_clk", "", "ao_misc_apb_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["mcu_ao_ref", "", "pad_ref_clk", "", "", "", "", "", "", "Y", "", "", "pmu_mcu_clkgate_req", "", "internal"],
        ["S32KCLK", "", "pad_ref_clk", "", "", "clk_divider", "10", "5", "OCC", "", "", "", "", "", "output"],
        ["REFCLK", "", "pad_ref_clk", "", "", "", "", "", "", "", "", "", "", "", "output"],
        ["SECENCREFCLK", "", "pad_ref_clk", "", "", "", "", "", "", "", "", "", "", "", "internal"],
        ["TRACECLKIN", "", "cs_pll_clk", "", "", "clk_divider", "8", "6", "OCC", "Y", "Y", "", "", "", "output"],
        ["SYSPLL", "", "cs_pll_clk", "", "", "", "", "", "", "Y", "Y", "", "", "", "output"],
        ["soc_ref_clk", "", "pad_ref_clk", "", "", "", "", "", "", "Y", "Y", "", "pmu_main_clkgate_req", "", "output"],
        ["ao_rom_divclk", "", "secencdivclk", "", "", "clk_divider_er", "8", "2", "OCC", "Y", "Y", "", "", "", "output"],
        ["ao_gpio_lb_det_clk", "", "pad_ref_clk", "", "", "", "", "", "", "Y", "", "", "", "", "output"],
        ["hsm_trng_smp_clk", "", "cs_pll_clk", "", "", "clk_divider", "8", "6", "OCC", "Y", "Y", "", "", "", "output"],
        ["cs_pll_test_clk_out", "", "cs_pll_clk", "", "", "clk_divider", "8", "60", "OCC", "Y", "Y", "", "", "", "output"],
    ]
    for r in rows:
        ws.append(r)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    print(f"Created sample xlsx: {path}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) >= 2:
        input_path = sys.argv[1]
    else:
        input_path = os.path.join(script_dir, "input", "crg_clock_table.xlsx")

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        output_path = os.path.join(script_dir, "output", "crg_clock_tree.drawio")

    # 如果没有输入文件，创建示例
    if not os.path.exists(input_path):
        create_sample_xlsx(input_path)

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print("=" * 60)
    print("CRG Clock Tree -> Draw.io Generator")
    print("=" * 60)

    # 1. 解析表格
    print(f"\n[1/4] Parsing: {input_path}")
    parser = CrgExcelParser(input_path)
    rows = parser.parse()
    summary = parser.get_summary(rows)
    print(f"  Total signals: {summary['total']}")
    print(f"  Attributes: {summary['attrs']}")

    # 2. 构建图
    print("\n[2/4] Building graph...")
    graph = Graph()
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
    if ext in (".excalidraw", ".json"):
        renderer = ExcalidrawRenderer()
        renderer.render(graph, output_path, title="CRG Clock Tree")
        print("\n" + "=" * 60)
        print("Done! Open https://excalidraw.com and drag the file in")
        print("=" * 60)
    else:
        renderer = DrawioRenderer()
        renderer.render(graph, output_path, title="CRG Clock Tree")
        print("\n" + "=" * 60)
        print("Done! Open the file with https://app.diagrams.net")
        print("=" * 60)


if __name__ == "__main__":
    main()
