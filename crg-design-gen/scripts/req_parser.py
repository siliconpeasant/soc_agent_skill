"""
需求表解析器
适配用户的 CRG 需求表格格式（子系统、IP、时钟复位需求、备注）
"""
import re
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class ReqTableParser:
    """Parse CRG requirement table into structured clock/reset signals."""

    SUPPORTED_FORMATS = [".xlsx", ".xls", ".csv"]

    # Fuzzy column name aliases
    COL_ALIASES = {
        "subsystem": ["subsystem", "子系统", "模块", "module", "block", "系统"],
        "ip": ["ip", "IP", "模块名", "mod"],
        "signal": [
            "signal", "时钟复位需求", "信号名", "name", "信号",
            "时钟/复位", "时钟复位", "时钟 复位 需求",
        ],
        "note": ["note", "备注", "注释", "说明", "频率", "freq", "remark", "信息"],
    }

    def __init__(self, file_path: str, sheet_name: Optional[str] = None):
        self.file_path = Path(file_path)
        self.sheet_name = sheet_name
        self.col_map: Dict[str, str] = {}

        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if self.file_path.suffix not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {self.file_path.suffix}")

    def _read_raw(self) -> pd.DataFrame:
        suffix = self.file_path.suffix
        if suffix in [".xlsx", ".xls"]:
            if self.sheet_name:
                df = pd.read_excel(self.file_path, sheet_name=self.sheet_name)
            else:
                xls = pd.ExcelFile(self.file_path)
                self.sheet_name = xls.sheet_names[0]
                df = pd.read_excel(self.file_path, sheet_name=self.sheet_name)
        else:
            df = pd.read_csv(self.file_path)
        print(f"Loaded {len(df)} rows from {self.file_path.name} (sheet: {self.sheet_name})")
        return df

    def _detect_columns(self, df: pd.DataFrame):
        """Fuzzy-match column names to standard keys."""
        cols_lower = {str(c).strip().lower(): c for c in df.columns}
        for std_name, aliases in self.COL_ALIASES.items():
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in cols_lower:
                    self.col_map[std_name] = cols_lower[alias_lower]
                    break

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df.columns = [str(c).strip() for c in df.columns]
        self._detect_columns(df)

        sig_col = self.col_map.get("signal")
        if not sig_col or sig_col not in df.columns:
            raise ValueError(
                f"Required column 'signal' (时钟复位需求) not found. "
                f"Available: {list(df.columns)}"
            )

        # Forward-fill subsystem column (merged cells in Excel)
        sub_col = self.col_map.get("subsystem")
        if sub_col and sub_col in df.columns:
            df[sub_col] = df[sub_col].ffill()

        # Drop rows with empty signal name
        df = df.dropna(subset=[sig_col])
        df = df[df[sig_col].astype(str).str.strip() != ""]

        # Drop header duplicate rows
        df = df[~df[sig_col].astype(str).str.upper().isin(
            [c.upper() for c in df.columns if isinstance(c, str)]
        )]

        return df.reset_index(drop=True)

    def parse(self) -> Dict[str, List[Dict]]:
        """
        Parse requirement table.

        Returns:
            {"clocks": [...], "resets": [...]}
            Each dict contains: name, subsystem, ip, note, freq_mhz, freqs, is_pad
        """
        df = self._read_raw()
        df = self._clean(df)

        sig_col = self.col_map["signal"]
        sub_col = self.col_map.get("subsystem")
        ip_col = self.col_map.get("ip")
        note_col = self.col_map.get("note")

        signals = {"clocks": [], "resets": []}

        for _, row in df.iterrows():
            name = str(row[sig_col]).strip()
            if not name or name.lower() in ("nan", "<na>", "none"):
                continue

            subsystem = str(row.get(sub_col, "")).strip() if sub_col else ""
            ip = str(row.get(ip_col, "")).strip() if ip_col else ""
            note = str(row.get(note_col, "")).strip() if note_col else ""

            sig_type = classify_signal(name)
            if sig_type == "clock":
                freqs = extract_frequencies(note)
                signals["clocks"].append({
                    "name": name,
                    "subsystem": subsystem,
                    "ip": ip,
                    "note": note,
                    "freq_mhz": freqs[0] if freqs else None,
                    "freqs": freqs,
                    "is_pad": is_pad_clock(name, note),
                })
            elif sig_type == "reset":
                signals["resets"].append({
                    "name": name,
                    "subsystem": subsystem,
                    "ip": ip,
                    "note": note,
                })

        print(f"Parsed {len(signals['clocks'])} clocks, {len(signals['resets'])} resets")
        return signals


# ---------------------------------------------------------------------------
# Utility functions (also used by other modules)
# ---------------------------------------------------------------------------

CLK_SUFFIXES = ("_clk", "_pclk", "_aclk", "_hclk", "_fclk", "_tck")
RST_SUFFIXES = ("_rst_n", "_rstn", "_prstn", "_srst_n", "_nrst")
RST_KEYWORDS = ("poreset", "reset", "trst", "srst", "nreset", "nrst")
PAD_KEYWORDS = ("pad", "xtal", "osc", "ref")


def classify_signal(name: str) -> str:
    """Classify a signal name as 'clock', 'reset', or 'unknown'."""
    n = name.lower()

    for kw in RST_KEYWORDS:
        if kw in n:
            return "reset"
    for suffix in RST_SUFFIXES:
        if n.endswith(suffix):
            return "reset"
    for suffix in CLK_SUFFIXES:
        if n.endswith(suffix):
            return "clock"

    if "clk" in n:
        return "clock"
    if "rst" in n:
        return "reset"

    return "unknown"


def is_pad_clock(name: str, note: str) -> bool:
    """Heuristic: is this an external input clock source?"""
    n = name.lower()
    for kw in PAD_KEYWORDS:
        if kw in n:
            return True
    if note and ("外部" in note or "pad" in note.lower() or "输入" in note):
        return True
    return False


def extract_frequencies(note: str) -> Optional[Tuple[float, ...]]:
    """
    Extract frequency values (in MHz) from a note string.

    Supports:
      - '200MHz', '3 Mhz', '1000MHz'
      - '20/25Mhz'  -> (20.0, 25.0)
      - '25 / 8 = 3.125' -> (25.0, 3.125)
    """
    if pd.isna(note) or not str(note).strip():
        return None

    s = str(note).strip()
    freqs = []

    # Pattern: number + optional space + unit
    pattern = r"(\d+(?:\.\d+)?)\s*(GHz|MHz|KHz|Hz|ghz|mhz|khz|hz)"
    for m in re.finditer(pattern, s, re.IGNORECASE):
        val = float(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("ghz"):
            val *= 1000.0
        elif unit.startswith("mhz"):
            pass
        elif unit.startswith("khz"):
            val /= 1000.0
        elif unit == "hz":
            val /= 1_000_000.0
        freqs.append(val)

    if freqs:
        return tuple(freqs)

    # Fallback: plain numbers (only if no units found)
    nums = re.findall(r"\d+\.?\d*", s)
    if nums:
        return tuple(float(n) for n in nums)

    return None
