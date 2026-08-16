#!/usr/bin/env python3
"""
CRG Design Generator MCP Server

Merged frontend CRG design flow:
  - stage 1: requirement table → design tables + PLL report
  - stage 2: design tables → Draw.io / Excalidraw diagrams

Former skills: crg-req-to-design, cr-tree-diag-gen.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

mcp = FastMCP(
    name="crg-design-gen",
    instructions=(
        "CRG 前端设计：需求表→时钟/复位设计表与 PLL 报告；"
        "设计表→Draw.io/Excalidraw 拓扑图。"
        "两阶段可分开调用；一键 pipeline 仅作草稿（设计表须人工评审）。"
        "不生成 CRG RTL（请用 crg-gen）。"
    ),
)


# ---------------------------------------------------------------------------
# Stage 1 — requirement → design tables
# ---------------------------------------------------------------------------


def _generate_design(input_path: str, output_dir: Optional[str] = None) -> str:
    try:
        from scripts.req_parser import ReqTableParser
        from scripts.pll_recommender import PllRecommender
        from scripts.reset_table_gen import ResetTreeGenerator
        from scripts.crg_config_writer import write_all_design_outputs
    except ImportError as exc:
        raise RuntimeError(
            "missing CRG design runtime dependencies; pip install pandas openpyxl"
        ) from exc

    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise ValueError(f"input file not found: {input_file}")

    if not output_dir:
        output_dir = str(input_file.parent / f"{input_file.stem}_design")
    else:
        output_dir = str(Path(output_dir).expanduser().resolve())
    os.makedirs(output_dir, exist_ok=True)

    parser = ReqTableParser(str(input_file))
    signals = parser.parse()

    recommender = PllRecommender(signals["clocks"])
    clock_result = recommender.recommend()

    reset_gen = ResetTreeGenerator(signals["resets"])
    reset_rows = reset_gen.generate()

    # design_name for crg-gen top_info / workbook stem
    design_name = re.sub(r"[^\w]+", "_", input_file.stem).strip("_") or "demo_crg"
    if design_name.lower().endswith("_req") or design_name.lower().endswith("_table"):
        design_name = re.sub(r"_(req|table)$", "", design_name, flags=re.I) or design_name
    design_name = design_name[:48] or "demo_crg"

    report_parts = [
        clock_result["report"],
        "",
        "=== Reset Tree Summary ===",
        f"Total resets: {len(signals['resets'])}",
        f"Root reset: {reset_gen.root_name or 'N/A'}",
    ]
    for r in reset_rows:
        line = f"  {r['NAME']:30s}  attr={r['ATTR']:8s}"
        if r.get("SRC0"):
            line += f"  src0={r['SRC0']}"
        report_parts.append(line)
    report_parts.extend(
        [
            "",
            "=== Handoff to crg-gen ===",
            f"Primary workbook: {design_name}_crg.xlsx",
            "Edit top_info / user_defined_reg / user_code / user_sdc as needed,",
            "then: crg-gen.crg_gen(excel_file=<that xlsx>, output_dir=...)",
        ]
    )
    report_text = "\n".join(report_parts)

    paths = write_all_design_outputs(
        output_dir,
        clock_result["clock_rows"],
        reset_rows,
        report_text,
        design_name=design_name,
    )

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

    lines.extend(
        [
            "",
            "Generated files (crg-gen ready):",
            f"  - PRIMARY crg-gen input: {paths['crg_config']}",
            f"  - Clock design (tree):   {paths['clock_design']}",
            f"  - Reset design (tree):   {paths['reset_design']}",
            f"  - Report:                {paths['report']}",
            f"  - Handoff notes:         {paths['readme']}",
            "",
            "Next: edit the PRIMARY xlsx, then run crg-gen on it.",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 2 — design table → diagrams
# ---------------------------------------------------------------------------


def _generate_tree(
    input_path: str,
    output_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    try:
        from scripts.parser import CrgExcelParser
        from scripts.graph import Graph
        from scripts.layout import HierarchicalLayout
        from scripts.renderer import DrawioRenderer
        from scripts.excalidraw_renderer import ExcalidrawRenderer
    except ImportError as exc:
        raise RuntimeError(
            "missing diagram runtime dependencies; pip install pandas openpyxl"
        ) from exc

    input_file = Path(input_path).expanduser().resolve()
    if not input_file.is_file():
        raise ValueError(f"input file not found: {input_file}")

    if output_path:
        output_paths = [output_path]
    else:
        input_stem = input_file.stem
        if input_stem.endswith("_table"):
            output_stem = input_stem[:-6] + "_tree"
        else:
            output_stem = input_stem + "_tree"
        if output_dir:
            output_dir_path = str(Path(output_dir).expanduser().resolve())
        else:
            output_dir_path = str(input_file.parent / f"{input_stem}_diagram")
        output_paths = [
            os.path.join(output_dir_path, output_stem + ".drawio"),
            os.path.join(output_dir_path, output_stem + ".excalidraw"),
        ]

    parser = CrgExcelParser(str(input_file))
    rows = parser.parse()
    summary = parser.get_summary(rows)

    is_reset = (
        any("SOFT_DFLT" in str(k).upper() for k in rows[0].keys()) if rows else False
    )
    tree_type = "Reset Tree" if is_reset else "Clock Tree"

    graph = Graph()
    if is_reset:
        graph.build_reset_tree_from_rows(rows)
    else:
        graph.build_from_rows(rows)

    errors = graph.validate()
    warnings_text = "\n".join(f"  - {e}" for e in errors) if errors else "None"

    layout = HierarchicalLayout(
        level_spacing=280,
        node_spacing=70,
        start_x=80,
        start_y=120,
    )
    layout.compute(graph)

    results = []
    title = f"CRG {tree_type}"
    for out_path in output_paths:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        ext = os.path.splitext(out_path)[1].lower()
        if ext in (".excalidraw", ".json"):
            ExcalidrawRenderer().render(graph, out_path, title=title)
            results.append(f"Excalidraw: {out_path}")
        else:
            DrawioRenderer().render(graph, out_path, title=title)
            results.append(f"Draw.io: {out_path}")

    return (
        f"Generated {tree_type}\n"
        f"Signals: {summary['total']}, Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}\n"
        f"Attributes: {summary['attrs']}\n"
        f"Warnings: {warnings_text}\n"
        f"Outputs:\n" + "\n".join(f"  - {r}" for r in results)
    )


def _default_tree_path(input_path: str, ext: str) -> str:
    input_file = Path(input_path).expanduser().resolve()
    input_stem = input_file.stem
    if input_stem.endswith("_table"):
        output_stem = input_stem[:-6] + "_tree"
    else:
        output_stem = input_stem + "_tree"
    return str(
        input_file.parent / f"{input_stem}_diagram" / (output_stem + ext)
    )


# ---------------------------------------------------------------------------
# Tools (stable names for agents / old docs)
# ---------------------------------------------------------------------------


@mcp.tool()
def crg_req_to_design(input_path: str, output_dir: str = None) -> str:
    """从 CRG 需求表生成时钟/复位设计表，并推荐 PLL 架构。

    Args:
        input_path: 需求表（.xlsx / .xls / .csv）
        output_dir: 输出目录；默认 <stem>_design
    """
    return _generate_design(input_path, output_dir=output_dir)


@mcp.tool()
def cr_tree_diag_gen(input_path: str, output_dir: str = None) -> str:
    """从已评审的时钟/复位设计表生成拓扑图（drawio + excalidraw）。

    Args:
        input_path: 设计表 Excel（.xlsx）
        output_dir: 输出目录；默认 <stem>_diagram
    """
    return _generate_tree(input_path, output_dir=output_dir)


@mcp.tool()
def cr_tree_diag_gen_drawio(input_path: str, output_path: str = None) -> str:
    """从设计表生成 Draw.io 图。

    Args:
        input_path: 设计表 Excel
        output_path: .drawio 路径；默认自动推导
    """
    if not output_path:
        output_path = _default_tree_path(input_path, ".drawio")
    return _generate_tree(input_path, output_path=output_path)


@mcp.tool()
def cr_tree_diag_gen_excalidraw(input_path: str, output_path: str = None) -> str:
    """从设计表生成 Excalidraw 图。

    Args:
        input_path: 设计表 Excel
        output_path: .excalidraw 路径；默认自动推导
    """
    if not output_path:
        output_path = _default_tree_path(input_path, ".excalidraw")
    return _generate_tree(input_path, output_path=output_path)


@mcp.tool()
def crg_req_pipeline(
    input_path: str,
    output_dir: str = None,
    with_diagram: bool = False,
) -> str:
    """需求表一键流水线：设计表（+ 可选拓扑图草稿）。

    设计表在 RTL/正式出图前须人工评审。with_diagram=true 时基于**未评审**
    自动 design 表出图，输出中标记 UNREVIEWED。

    Args:
        input_path: 需求表
        output_dir: 设计表输出目录；默认 <stem>_design
        with_diagram: 是否在 design 后立刻画图（默认 false）
    """
    design_text = _generate_design(input_path, output_dir=output_dir)
    input_file = Path(input_path).expanduser().resolve()
    if not output_dir:
        design_dir = input_file.parent / f"{input_file.stem}_design"
    else:
        design_dir = Path(output_dir).expanduser().resolve()

    lines = [
        "=== crg-design-gen pipeline ===",
        design_text,
        "",
        "NOTE: Review clock_design.xlsx / reset_design.xlsx before RTL (crg-gen)",
        "      or treating diagrams as approved.",
    ]

    if with_diagram:
        clock_xlsx = design_dir / "clock_design.xlsx"
        reset_xlsx = design_dir / "reset_design.xlsx"
        diag_dir = str(design_dir / "diagrams_unreviewed")
        lines.append("")
        lines.append("=== Diagrams from UNREVIEWED design tables ===")
        if clock_xlsx.is_file():
            lines.append(_generate_tree(str(clock_xlsx), output_dir=diag_dir))
        if reset_xlsx.is_file():
            lines.append(_generate_tree(str(reset_xlsx), output_dir=diag_dir))
        lines.append(
            "WARNING: diagrams are UNREVIEWED drafts — re-run cr_tree_diag_gen after review."
        )

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
