"""
PLL 推荐器与时钟树架构生成
基于整数分频关系匹配源时钟，最小化 PLL 数量。
"""
import math
from typing import List, Dict, Optional, Tuple


class PllRecommender:
    """Recommend PLL count and generate clock tree design rows."""

    # Frequency matching tolerance (5%)
    FREQ_TOLERANCE = 0.05
    MAX_DIV = 64

    def __init__(self, clocks: List[Dict]):
        self.clocks = clocks
        self.pad_clocks = [c for c in clocks if c.get("is_pad")]
        self.internal_clocks = [c for c in clocks if not c.get("is_pad")]
        self.plls: List[Dict] = []

    @staticmethod
    def find_division(src_freq: float, tgt_freq: float,
                      tolerance: float = FREQ_TOLERANCE,
                      max_div: int = MAX_DIV) -> Optional[Tuple[int, float]]:
        """
        Find integer division ratio from src_freq to tgt_freq.

        Returns (div, relative_error) if valid, else None.
        """
        if src_freq <= 0 or tgt_freq <= 0:
            return None
        if src_freq < tgt_freq * (1 - tolerance):
            return None

        best = None
        for div in range(1, max_div + 1):
            divided = src_freq / div
            error = abs(divided - tgt_freq) / tgt_freq
            if error <= tolerance:
                if best is None or error < best[1]:
                    best = (div, error)
        return best

    def recommend(self) -> Dict:
        """
        Run full analysis.

        Returns dict with keys:
          - plls: list of PLL dicts {name, freq_mhz, outputs}
          - pad_clocks: list of pad clock dicts
          - clock_rows: list of design-table row dicts
          - report: str (human-readable summary)
        """
        # ------------------------------------------------------------------
        # Step 1: Match internal clocks to pad sources
        # ------------------------------------------------------------------
        unmatched = []
        for c in self.internal_clocks:
            tgt_freq = c.get("freq_mhz")
            if tgt_freq is None:
                unmatched.append(c)
                continue

            best_source = None
            best_div = None
            best_error = float("inf")

            for pad in self.pad_clocks:
                pad_freq = pad.get("freq_mhz")
                if pad_freq is None:
                    continue
                div_info = self.find_division(pad_freq, tgt_freq)
                if div_info:
                    div, err = div_info
                    if err < best_error:
                        best_error = err
                        best_source = pad
                        best_div = div

            if best_source:
                c["source"] = best_source["name"]
                c["source_type"] = "pad"
                c["div"] = best_div
            else:
                unmatched.append(c)

        # ------------------------------------------------------------------
        # Step 2: Group unmatched clocks by frequency
        # ------------------------------------------------------------------
        freq_groups: Dict[float, List[Dict]] = {}
        for c in unmatched:
            freq = c.get("freq_mhz")
            if freq is None:
                freq = 0.0
            key = round(freq, 2)
            freq_groups.setdefault(key, []).append(c)

        # ------------------------------------------------------------------
        # Step 3: Recommend PLLs (higher freq first)
        # ------------------------------------------------------------------
        sorted_freqs = sorted(freq_groups.keys(), reverse=True)
        pll_idx = 0

        for freq in sorted_freqs:
            clocks_at_freq = freq_groups[freq]

            # Try to assign to existing PLLs (higher freq PLLs first)
            for pll in self.plls:
                pll_freq = pll["freq_mhz"]
                for c in clocks_at_freq:
                    if "source" in c:
                        continue
                    tgt_freq = c.get("freq_mhz")
                    if tgt_freq is None:
                        continue
                    div_info = self.find_division(pll_freq, tgt_freq)
                    if div_info:
                        div, _ = div_info
                        c["source"] = pll["name"]
                        c["source_type"] = "pll"
                        c["div"] = div
                        pll["outputs"].append(c)

            # Create new PLL for remaining unassigned clocks
            remaining = [c for c in clocks_at_freq if "source" not in c]
            if remaining:
                pll_freq = remaining[0].get("freq_mhz")
                if pll_freq is None or pll_freq <= 0:
                    # No frequency info: leave source empty for manual assignment
                    for c in remaining:
                        c["source"] = ""
                        c["source_type"] = "unknown"
                        c["div"] = 1
                else:
                    pll_name = f"pll{pll_idx}_clk"
                    pll = {
                        "name": pll_name,
                        "freq_mhz": pll_freq,
                        "outputs": [],
                    }
                    for c in remaining:
                        c["source"] = pll_name
                        c["source_type"] = "pll"
                        c["div"] = 1
                        pll["outputs"].append(c)
                    self.plls.append(pll)
                    pll_idx += 1

        # ------------------------------------------------------------------
        # Step 4: Build design-table rows
        # ------------------------------------------------------------------
        rows = []

        # Pad input nodes
        for pad in self.pad_clocks:
            rows.append(self._make_clock_row(
                name=pad["name"],
                attr="input",
                note=pad.get("note", ""),
            ))

        # PLL internal nodes
        for pll in self.plls:
            freq_str = f"{pll['freq_mhz']}MHz" if pll.get("freq_mhz") is not None else ""
            rows.append(self._make_clock_row(
                name=pll["name"],
                attr="internal",
                note=freq_str,
            ))

        # Target/output clocks
        for c in self.internal_clocks:
            src = c.get("source", "")
            div = c.get("div", 1)

            div_flag = "clk_divider" if div > 1 else ""
            div_width = str(math.ceil(math.log2(div + 1))) if div > 1 else ""
            div_dflt = str(int(div)) if div > 1 else ""

            rows.append(self._make_clock_row(
                name=c["name"],
                attr="output",
                src0=src,
                div=div_flag,
                div_width=div_width,
                div_dflt=div_dflt,
                note=c.get("note", ""),
            ))

        # ------------------------------------------------------------------
        # Step 5: Build report
        # ------------------------------------------------------------------
        report_lines = [
            "=== CRG Clock Architecture Analysis Report ===",
            "",
            f"Total clocks: {len(self.clocks)}",
            f"  Pad input clocks: {len(self.pad_clocks)}",
            f"  Internal/output clocks: {len(self.internal_clocks)}",
            f"Recommended PLLs: {len(self.plls)}",
        ]

        for pll in self.plls:
            report_lines.append(f"  - {pll['name']}: {pll['freq_mhz']}MHz")
            for out in pll["outputs"]:
                d = out.get("div", 1)
                div_str = f" /{d}" if d > 1 else ""
                report_lines.append(f"      -> {out['name']}{div_str}")

        if self.pad_clocks:
            report_lines.append("")
            report_lines.append("Pad-to-clock derivations:")
            for c in self.internal_clocks:
                if c.get("source_type") == "pad":
                    d = c.get("div", 1)
                    div_str = f" /{d}" if d > 1 else ""
                    pad_freq = next(
                        (p.get("freq_mhz", "?") for p in self.pad_clocks
                         if p["name"] == c["source"]), "?"
                    )
                    report_lines.append(
                        f"  {c['source']} ({pad_freq}MHz){div_str} -> {c['name']}"
                    )

        report = "\n".join(report_lines)

        return {
            "plls": self.plls,
            "pad_clocks": self.pad_clocks,
            "clock_rows": rows,
            "report": report,
        }

    @staticmethod
    def _make_clock_row(
        name: str,
        attr: str = "",
        src0: str = "",
        src1: str = "",
        mux_dflt: str = "",
        div: str = "",
        div_width: str = "",
        div_dflt: str = "",
        occ: str = "",
        icg: str = "",
        icg_dflt: str = "",
        note: str = "",
    ) -> Dict:
        # Column order matches cr_tree_diag_gen example template:
        # NAME, SEL, SRC0, SRC1, MUX_DFLT, DIV, DIV_WIDTH, DIV_DFLT, OCC, ICG, ICG_DFLT, ATTR, NOTE
        return {
            "NAME": name,
            "SEL": "",
            "SRC0": src0,
            "SRC1": src1,
            "MUX_DFLT": mux_dflt,
            "DIV": div,
            "DIV_WIDTH": div_width,
            "DIV_DFLT": div_dflt,
            "OCC": occ,
            "ICG": icg,
            "ICG_DFLT": icg_dflt,
            "ATTR": attr,
            "NOTE": note,
        }
