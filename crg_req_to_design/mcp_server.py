#!/usr/bin/env python3
"""
CRG Requirement to Design Table MCP Server

轻量级 MCP Wrapper，暴露 crg_req_to_design 的核心功能。

运行方式:
    python3 mcp_server.py          # stdio transport (默认)
"""

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# 路径推导：确保能导入同目录下的 scripts 包
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="crg-req-to-design",
    instructions=(
        "CRG 需求表到设计表转换器。\n"
        "将需求表（子系统、IP、时钟/复位信号、备注/频率）转换为时钟树设计表和复位树设计表，\n"
        "并推荐 PLL 数量与时钟树架构。"
    ),
)


# ---------------------------------------------------------------------------
# 核心生成逻辑
# ---------------------------------------------------------------------------
def _generate(input_path: str, output_dir: str = None) -> str:
    """核心生成逻辑"""
    # 延迟导入，避免 MCP 启动时加载失败
    from scripts.req_parser import ReqTableParser
    from scripts.pll_recommender import PllRecommender
    from scripts.reset_table_gen import ResetTreeGenerator

    if not os.path.exists(input_path):
        return f"Error: Input file not found: {input_path}"

    # 推导输出目录
    if not output_dir:
        output_dir = str(SCRIPT_DIR / "output")
    os.makedirs(output_dir, exist_ok=True)

    try:
        import pandas as pd
    except ImportError:
        return "Error: pandas is required. Install with: pip install pandas openpyxl"

    # 解析需求表
    parser = ReqTableParser(input_path)
    signals = parser.parse()

    # 推荐 PLL 架构并生成时钟设计表
    recommender = PllRecommender(signals["clocks"])
    clock_result = recommender.recommend()

    # 生成复位设计表
    reset_gen = ResetTreeGenerator(signals["resets"])
    reset_rows = reset_gen.generate()

    # 写入输出文件
    clock_df = pd.DataFrame(clock_result["clock_rows"]).fillna("")
    reset_df = pd.DataFrame(reset_rows).fillna("")

    clock_path = os.path.join(output_dir, "clock_design.xlsx")
    reset_path = os.path.join(output_dir, "reset_design.xlsx")
    report_path = os.path.join(output_dir, "crg_report.txt")

    clock_df.to_excel(clock_path, index=False, na_rep="")
    reset_df.to_excel(reset_path, index=False, na_rep="")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(clock_result["report"])
        f.write("\n\n")
        f.write("=== Reset Tree Summary ===\n")
        f.write(f"Total resets: {len(signals['resets'])}\n")
        f.write(f"Root reset: {reset_gen.root_name or 'N/A'}\n")
        for r in reset_rows:
            f.write(f"  {r['NAME']:30s}  attr={r['ATTR']:8s}")
            if r.get("SRC0"):
                f.write(f"  src0={r['SRC0']}")
            f.write("\n")

    # 汇总输出
    lines = [
        f"Parsed {len(signals['clocks'])} clocks, {len(signals['resets'])} resets",
        f"Recommended PLLs: {len(clock_result['plls'])}",
    ]
    for pll in clock_result["plls"]:
        lines.append(f"  - {pll['name']}: {pll['freq_mhz']}MHz")
        for out in pll["outputs"]:
            div_str = f" /{out.get('div', 1)}" if out.get("div", 1) > 1 else ""
            lines.append(f"      -> {out['name']}{div_str}")

    if any(c.get("source_type") == "pad" for c in signals["clocks"] if not c.get("is_pad")):
        lines.append("")
        lines.append("Pad-to-clock derivations:")
        for c in signals["clocks"]:
            if not c.get("is_pad") and c.get("source_type") == "pad":
                div_str = f" /{c.get('div', 1)}" if c.get("div", 1) > 1 else ""
                lines.append(f"  {c['source']}{div_str} -> {c['name']}")

    lines.extend([
        "",
        "Generated files:",
        f"  - Clock design: {clock_path}",
        f"  - Reset design: {reset_path}",
        f"  - Report:       {report_path}",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def crg_req_to_design(input_path: str, output_dir: str = None) -> str:
    """从 CRG 需求表生成时钟树设计表和复位树设计表，并推荐 PLL 架构。

    Args:
        input_path: 输入需求表文件路径（.xlsx / .xls / .csv）
        output_dir: 输出目录，留空则使用内置 output/ 目录
    """
    return _generate(input_path, output_dir=output_dir)


if __name__ == "__main__":
    mcp.run()
