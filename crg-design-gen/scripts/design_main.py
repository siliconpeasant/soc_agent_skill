#!/usr/bin/env python3
"""
CLI: CRG requirement table → crg-gen-ready workbook (+ tree views + report).

Usage:
    python design_main.py <req_table.xlsx> [output_dir]

Outputs (under output_dir):
    - <design>_crg.xlsx     PRIMARY input for crg-gen (edit then generate RTL)
    - clock_design.xlsx     slim view for tree diagrams
    - reset_design.xlsx
    - crg_report.txt
    - README_CRG_HANDOFF.txt
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from req_parser import ReqTableParser
from pll_recommender import PllRecommender
from reset_table_gen import ResetTreeGenerator
from crg_config_writer import write_all_design_outputs


def main():
    if len(sys.argv) < 2:
        print("Usage: python design_main.py <req_table.xlsx> [output_dir]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"

    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print(f"\n[1/4] Parsing requirement table: {input_path}")
    parser = ReqTableParser(input_path)
    signals = parser.parse()

    print("[2/4] Analyzing clock frequencies and recommending PLLs...")
    recommender = PllRecommender(signals["clocks"])
    clock_result = recommender.recommend()

    print("[3/4] Generating reset tree design table...")
    reset_gen = ResetTreeGenerator(signals["resets"])
    reset_rows = reset_gen.generate()

    print("[4/4] Writing crg-gen workbook + companion files...")
    stem = Path(input_path).stem
    design_name = re.sub(r"[^\w]+", "_", stem).strip("_") or "demo_crg"
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
            "Edit sheets as needed, then run crg-gen on that file.",
        ]
    )

    paths = write_all_design_outputs(
        output_dir,
        clock_result["clock_rows"],
        reset_rows,
        "\n".join(report_parts),
        design_name=design_name,
    )

    print(f"\n{'='*50}")
    print("Done! Generated files:")
    print(f"  PRIMARY (crg-gen): {paths['crg_config']}")
    print(f"  Clock design:      {paths['clock_design']}")
    print(f"  Reset design:      {paths['reset_design']}")
    print(f"  Report:            {paths['report']}")
    print(f"  Handoff notes:     {paths['readme']}")
    print(f"\nRecommended PLLs: {len(clock_result['plls'])}")
    for pll in clock_result["plls"]:
        print(f"  - {pll['name']}: {pll['freq_mhz']}MHz")
    print(f"{'='*50}")
    print("\nNext:")
    print(f"  1) Edit {paths['crg_config']}")
    print(f"  2) After review, feed {paths['crg_config']} to crg-gen if available")
    print(f"  3) Optional trees: python3 crg-design-gen/scripts/tree_main.py {paths['clock_design']}")


if __name__ == "__main__":
    main()
