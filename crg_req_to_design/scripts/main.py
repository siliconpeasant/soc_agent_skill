"""
CLI entry point for CRG Requirement -> Design Table conversion.

Usage:
    python main.py <req_table.xlsx> [output_dir]

Outputs:
    - clock_design.xlsx   (clock tree design table)
    - reset_design.xlsx   (reset tree design table)
    - crg_report.txt      (PLL recommendation & architecture summary)
"""
import sys
import os
from pathlib import Path

# Allow running from scripts/ directly
sys.path.insert(0, str(Path(__file__).parent))

from req_parser import ReqTableParser
from pll_recommender import PllRecommender
from reset_table_gen import ResetTreeGenerator


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <req_table.xlsx> [output_dir]")
        print("")
        print("  req_table.xlsx   Requirement table (subsystem, IP, signal, note)")
        print("  output_dir       Output directory (default: ./output)")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"

    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Parse requirement table
    # ------------------------------------------------------------------
    print(f"\n[1/4] Parsing requirement table: {input_path}")
    parser = ReqTableParser(input_path)
    signals = parser.parse()

    # ------------------------------------------------------------------
    # Recommend PLL architecture & generate clock design table
    # ------------------------------------------------------------------
    print("[2/4] Analyzing clock frequencies and recommending PLLs...")
    recommender = PllRecommender(signals["clocks"])
    clock_result = recommender.recommend()

    # ------------------------------------------------------------------
    # Generate reset design table
    # ------------------------------------------------------------------
    print("[3/4] Generating reset tree design table...")
    reset_gen = ResetTreeGenerator(signals["resets"])
    reset_rows = reset_gen.generate()

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    print("[4/4] Writing output files...")

    try:
        import pandas as pd
    except ImportError:
        print("Error: pandas is required. Install with: pip install pandas openpyxl")
        sys.exit(1)

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

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'='*50}")
    print("Done! Generated files:")
    print(f"  Clock design : {clock_path}")
    print(f"  Reset design : {reset_path}")
    print(f"  Report       : {report_path}")
    print(f"\nRecommended PLLs: {len(clock_result['plls'])}")
    for pll in clock_result["plls"]:
        print(f"  - {pll['name']}: {pll['freq_mhz']}MHz")
    print(f"{'='*50}\n")

    # Suggest next step
    crg_drawio_dir = Path(__file__).parent.parent.parent
    crg_tree_dir = crg_drawio_dir / "cr_tree_diag_gen"
    if crg_tree_dir.exists():
        print("Next step: generate diagram with cr_tree_diag_gen")
        print(f"  python {crg_tree_dir / 'scripts' / 'main.py'} {clock_path}")
        print(f"  python {crg_tree_dir / 'scripts' / 'main.py'} {reset_path}")


if __name__ == "__main__":
    main()
