#!/usr/bin/env python3
"""Write crg-gen-compatible Excel workbooks from design-stage clock/reset rows.

Primary output matches crg-gen template sheets so the file can be edited and
fed straight to crg-gen (top_info / clk_gen / rst_gen / stubs).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Column headers must match crg-gen/references/crg_demo.xlsx (clk_gen / rst_gen).
CLK_GEN_COLUMNS: List[str] = [
    "NAME",
    "SEL",
    "SRC0",
    "SRC1",
    "MUX_DFLT",
    "DIV",
    "DIV_WIDTH",
    "DIV_DFLT",
    "OCC/SCAN MUX",
    "ICG",
    "ICG_DFLT",
    "ICG_external",
    "ICG_internal",
    "CE_DISEN",
    "ATTR",
    "NOTE",
    "Clock Groups0",
    "Clock source",
    "Divider fadj",
    "Divider fadj_val",
    "divider_sync_clk",
    "DIV_VAL_TO_EN",
    "DIV_VAL_TO",
]

RST_GEN_COLUMNS: List[str] = [
    "NAME",
    "REG_NAME",
    "SOFT_LC",
    "SOFT_DFLT",
    "SRC0",
    "SRC1",
    "SRC2",
    "SRC3",
    "ASSERT_VALUE",
    "ARESET_RELAX_EN",
    "SYNC",
    "SYNC_CLK",
    "INOUT",
    "LOCK BIT OFFSET",
    "LOCK VALUE",
    "NOTE",
]

# Slim tables for cr_tree_diag_gen (topology only).
CLOCK_DESIGN_COLUMNS: List[str] = [
    "NAME",
    "SEL",
    "SRC0",
    "SRC1",
    "MUX_DFLT",
    "DIV",
    "DIV_WIDTH",
    "DIV_DFLT",
    "OCC",
    "ICG",
    "ICG_DFLT",
    "ATTR",
    "NOTE",
]

RESET_DESIGN_COLUMNS: List[str] = [
    "NAME",
    "SOFT_DFLT",
    "SRC0",
    "SRC1",
    "SRC2",
    "SRC3",
    "ATTR",
    "NOTE",
]

USER_REG_COLUMNS = [
    "register name",
    "address",
    "field name",
    "bit offset",
    "access",
    "default",
    "description",
    "LOCK BIT OFFSET",
    "LOCK VALUE",
]

USER_INTP_COLUMNS = [
    "interrupt name",
    "address",
    "field name",
    "width",
    "access",
    "default",
    "description",
    "LOCK BIT OFFSET",
    "LOCK VALUE",
]

USER_CODE_COLUMNS = ["TYPE", "LEFT", "RIGHT", "TOP_ATTR", "MODULE_ATTR"]

USER_SDC_COLUMNS = [
    "name",
    "type",
    "edge",
    "generate_point",
    "master_clock",
    "source",
    "frequency",
]


def _blank(row: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = row.get(k, "")
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() not in {"nan", "none"}:
            return s
    return ""


def _has_mhz_note(note: str) -> bool:
    return bool(re.search(r"\d+(\.\d+)?\s*[Mm][Hh][Zz]", note or ""))


def enrich_clock_row_for_crg(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map design-stage clock row → full clk_gen row (crg-gen columns)."""
    out = {c: "" for c in CLK_GEN_COLUMNS}
    name = _blank(row, "NAME", "name")
    attr = _blank(row, "ATTR", "attr").lower()
    note = _blank(row, "NOTE", "note")

    out["NAME"] = name
    out["SEL"] = _blank(row, "SEL")
    out["SRC0"] = _blank(row, "SRC0")
    out["SRC1"] = _blank(row, "SRC1")
    out["MUX_DFLT"] = _blank(row, "MUX_DFLT")
    out["DIV"] = _blank(row, "DIV")
    out["DIV_WIDTH"] = _blank(row, "DIV_WIDTH")
    out["DIV_DFLT"] = _blank(row, "DIV_DFLT")
    out["OCC/SCAN MUX"] = _blank(row, "OCC/SCAN MUX", "OCC", "occ")
    out["ICG"] = _blank(row, "ICG")
    out["ICG_DFLT"] = _blank(row, "ICG_DFLT")
    out["ICG_external"] = _blank(row, "ICG_external")
    out["ICG_internal"] = _blank(row, "ICG_internal")
    out["CE_DISEN"] = _blank(row, "CE_DISEN", "CE_EN")
    out["ATTR"] = attr
    out["NOTE"] = note
    out["Clock Groups0"] = _blank(row, "Clock Groups0", "clock_group0")
    out["Clock source"] = _blank(row, "Clock source", "clock_source")
    out["Divider fadj"] = _blank(row, "Divider fadj", "divider_fadj")
    out["Divider fadj_val"] = _blank(row, "Divider fadj_val", "divider_fadj_val")
    out["divider_sync_clk"] = _blank(row, "divider_sync_clk")
    out["DIV_VAL_TO_EN"] = _blank(row, "DIV_VAL_TO_EN")
    out["DIV_VAL_TO"] = _blank(row, "DIV_VAL_TO")

    # Auto SDC-oriented fields for primary inputs (user may edit later).
    if attr == "input" and name and name.lower() not in {"test_mode"}:
        if not out["Clock source"]:
            out["Clock source"] = f"source get_ports {{{name}}}"
        if not out["Clock Groups0"] and (_has_mhz_note(note) or True):
            # Always give a default group name for primary clocks; user can merge groups.
            out["Clock Groups0"] = f"{name}_group"

    return out


def enrich_reset_row_for_crg(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map design-stage reset row → full rst_gen row."""
    out = {c: "" for c in RST_GEN_COLUMNS}
    name = _blank(row, "NAME", "name")
    attr = _blank(row, "ATTR", "INOUT", "inout", "attr").lower()
    out["NAME"] = name
    out["REG_NAME"] = _blank(row, "REG_NAME")
    out["SOFT_LC"] = _blank(row, "SOFT_LC")
    out["SOFT_DFLT"] = _blank(row, "SOFT_DFLT")
    out["SRC0"] = _blank(row, "SRC0")
    out["SRC1"] = _blank(row, "SRC1")
    out["SRC2"] = _blank(row, "SRC2")
    out["SRC3"] = _blank(row, "SRC3")
    out["ASSERT_VALUE"] = _blank(row, "ASSERT_VALUE")
    out["ARESET_RELAX_EN"] = _blank(row, "ARESET_RELAX_EN")
    # Project convention: CRG never sync-releases. Empty SYNC means N.
    sync = _blank(row, "SYNC")
    inout = attr
    if inout == "output" and not sync:
        sync = "N"
    out["SYNC"] = sync
    out["SYNC_CLK"] = _blank(row, "SYNC_CLK")
    out["INOUT"] = attr
    out["LOCK BIT OFFSET"] = _blank(row, "LOCK BIT OFFSET", "lock_bit_offset")
    out["LOCK VALUE"] = _blank(row, "LOCK VALUE", "lock_value")
    out["NOTE"] = _blank(row, "NOTE", "note")
    return out


def to_clock_design_row(crg_clk_row: Dict[str, Any]) -> Dict[str, Any]:
    """clk_gen row → slim clock_design row for tree diagrams."""
    return {
        "NAME": _blank(crg_clk_row, "NAME"),
        "SEL": _blank(crg_clk_row, "SEL"),
        "SRC0": _blank(crg_clk_row, "SRC0"),
        "SRC1": _blank(crg_clk_row, "SRC1"),
        "MUX_DFLT": _blank(crg_clk_row, "MUX_DFLT"),
        "DIV": _blank(crg_clk_row, "DIV"),
        "DIV_WIDTH": _blank(crg_clk_row, "DIV_WIDTH"),
        "DIV_DFLT": _blank(crg_clk_row, "DIV_DFLT"),
        "OCC": _blank(crg_clk_row, "OCC/SCAN MUX", "OCC"),
        "ICG": _blank(crg_clk_row, "ICG"),
        "ICG_DFLT": _blank(crg_clk_row, "ICG_DFLT"),
        "ATTR": _blank(crg_clk_row, "ATTR"),
        "NOTE": _blank(crg_clk_row, "NOTE"),
    }


def to_reset_design_row(crg_rst_row: Dict[str, Any]) -> Dict[str, Any]:
    """rst_gen row → slim reset_design row for tree diagrams."""
    return {
        "NAME": _blank(crg_rst_row, "NAME"),
        "SOFT_DFLT": _blank(crg_rst_row, "SOFT_DFLT"),
        "SRC0": _blank(crg_rst_row, "SRC0"),
        "SRC1": _blank(crg_rst_row, "SRC1"),
        "SRC2": _blank(crg_rst_row, "SRC2"),
        "SRC3": _blank(crg_rst_row, "SRC3"),
        "ATTR": _blank(crg_rst_row, "INOUT", "ATTR"),
        "NOTE": _blank(crg_rst_row, "NOTE"),
    }


def ensure_clock_boilerplate(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prepend common crg-gen rows if missing (test_mode, clk_gen_rst_n)."""
    names = {_blank(r, "NAME").lower() for r in rows}
    head: List[Dict[str, Any]] = []
    if "test_mode" not in names:
        head.append(
            enrich_clock_row_for_crg(
                {"NAME": "test_mode", "ATTR": "input", "NOTE": "test_mode"}
            )
        )
    if "clk_gen_rst_n" not in names:
        head.append(
            enrich_clock_row_for_crg({"NAME": "clk_gen_rst_n", "ATTR": "internal"})
        )
    body = [enrich_clock_row_for_crg(r) for r in rows]
    return head + body


def ensure_reset_boilerplate(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    names = {_blank(r, "NAME").lower() for r in rows}
    head: List[Dict[str, Any]] = []
    if "test_mode" not in names:
        head.append(
            enrich_reset_row_for_crg({"NAME": "test_mode", "ATTR": "input"})
        )
    if "test_rstn" not in names and "test_rst_n" not in names:
        head.append(
            enrich_reset_row_for_crg({"NAME": "test_rstn", "ATTR": "input"})
        )
    body = [enrich_reset_row_for_crg(r) for r in rows]
    return head + body


def _top_info_rows(
    design_name: str,
    design_owner: str = "auto",
    protocol: str = "apb",
    design_hier: str = "",
) -> List[List[Any]]:
    """Rows for top_info sheet (first row becomes pandas header when crg-gen reads)."""
    hier = design_hier or f"u_{design_name}_top"
    # Mirror crg_demo.xlsx layout (label | value | comment)
    return [
        ["TOP_INFO", "", ""],
        ["design_owner", design_owner, ""],
        ["design name", design_name, ""],
        ["protocol", protocol, "ahb/apb/dab"],
        ["clk gen addr_ofst", "0x0", ""],
        ["rst gen addr_ofst", "0x800", ""],
        ["rst status addr_ofst", "0x1000", ""],
        ["user defined reg addr_ofst", "0x1600", ""],
        ["user defined intp addr_ofst", "0x2000", ""],
        ["delay_beat", "2", ""],
        ["design_hier", hier, "edit hierarchy for SDC pins"],
        ["clock_uncertainty_setup", "0.1", ""],
        ["clock_uncertainty_hold", "0.1", ""],
        ["clock_transition_rise_max", "0.1", ""],
        ["clock_transition_rise_min", "0.1", ""],
        ["clock_transition_fall_max", "0.1", ""],
        ["clock_transition_fall_min", "0.1", ""],
    ]


def write_crg_config_workbook(
    path: str | Path,
    clock_rows: Sequence[Dict[str, Any]],
    reset_rows: Sequence[Dict[str, Any]],
    *,
    design_name: str = "demo_crg",
    design_owner: str = "auto",
    protocol: str = "apb",
    design_hier: str = "",
) -> Path:
    """Write multi-sheet Excel consumable by crg-gen."""
    import pandas as pd

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Rows may already be full clk_gen/rst_gen dicts from ensure_*; still re-enrich safely.
    clk_full = [enrich_clock_row_for_crg(r) for r in clock_rows]
    rst_full = [enrich_reset_row_for_crg(r) for r in reset_rows]

    clk_df = pd.DataFrame(clk_full, columns=CLK_GEN_COLUMNS).fillna("")
    rst_df = pd.DataFrame(rst_full, columns=RST_GEN_COLUMNS).fillna("")
    top_df = pd.DataFrame(_top_info_rows(design_name, design_owner, protocol, design_hier))

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        # top_info: all rows stored (no pandas header) — matches crg_demo layout.
        top_df.to_excel(writer, sheet_name="top_info", index=False, header=False)
        clk_df.to_excel(writer, sheet_name="clk_gen", index=False)
        rst_df.to_excel(writer, sheet_name="rst_gen", index=False)
        pd.DataFrame(columns=USER_REG_COLUMNS).to_excel(
            writer, sheet_name="user_defined_reg", index=False
        )
        pd.DataFrame(columns=USER_INTP_COLUMNS).to_excel(
            writer, sheet_name="user_defined_intp", index=False
        )
        pd.DataFrame(columns=USER_CODE_COLUMNS).to_excel(
            writer, sheet_name="user_code", index=False
        )
        pd.DataFrame(columns=USER_SDC_COLUMNS).to_excel(
            writer, sheet_name="user_sdc", index=False
        )

    return out


def write_slim_design_tables(
    output_dir: str | Path,
    clock_rows_crg: Sequence[Dict[str, Any]],
    reset_rows_crg: Sequence[Dict[str, Any]],
) -> tuple[Path, Path]:
    """Companion slim xlsx for tree diagrams (optional views of the same data)."""
    import pandas as pd

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clock_path = out_dir / "clock_design.xlsx"
    reset_path = out_dir / "reset_design.xlsx"

    clock_slim = [to_clock_design_row(r) for r in clock_rows_crg]
    reset_slim = [to_reset_design_row(r) for r in reset_rows_crg]
    pd.DataFrame(clock_slim, columns=CLOCK_DESIGN_COLUMNS).fillna("").to_excel(
        clock_path, index=False, na_rep=""
    )
    pd.DataFrame(reset_slim, columns=RESET_DESIGN_COLUMNS).fillna("").to_excel(
        reset_path, index=False, na_rep=""
    )
    return clock_path, reset_path


def write_all_design_outputs(
    output_dir: str | Path,
    clock_rows: Sequence[Dict[str, Any]],
    reset_rows: Sequence[Dict[str, Any]],
    report_text: str,
    *,
    design_name: str = "demo_crg",
    design_owner: str = "auto",
    protocol: str = "apb",
    design_hier: str = "",
) -> Dict[str, Path]:
    """Write crg-gen workbook + slim design tables + report."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    clk_full = ensure_clock_boilerplate(list(clock_rows))
    rst_full = ensure_reset_boilerplate(list(reset_rows))

    crg_path = out_dir / f"{design_name}_crg.xlsx"
    write_crg_config_workbook(
        crg_path,
        clk_full,
        rst_full,
        design_name=design_name,
        design_owner=design_owner,
        protocol=protocol,
        design_hier=design_hier,
    )
    clock_path, reset_path = write_slim_design_tables(out_dir, clk_full, rst_full)
    report_path = out_dir / "crg_report.txt"
    report_path.write_text(report_text, encoding="utf-8")

    # Pointer file for humans
    readme = out_dir / "README_CRG_HANDOFF.txt"
    readme.write_text(
        "\n".join(
            [
                "CRG design-gen → crg-gen handoff",
                "================================",
                f"Primary (edit then run crg-gen): {crg_path.name}",
                "  sheets: top_info, clk_gen, rst_gen, user_defined_reg,",
                "          user_defined_intp, user_code, user_sdc",
                "",
                "Tree-diagram views (optional):",
                f"  {clock_path.name}",
                f"  {reset_path.name}",
                "",
                "Next:",
                f"  1) Review/edit {crg_path.name} (regs, user_code, SDC, hier).",
                f"  2) python .../crg_gen.py {crg_path.name} <out_dir>/",
                "  3) Or draw trees from clock_design.xlsx / reset_design.xlsx",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "crg_config": crg_path,
        "clock_design": clock_path,
        "reset_design": reset_path,
        "report": report_path,
        "readme": readme,
    }
