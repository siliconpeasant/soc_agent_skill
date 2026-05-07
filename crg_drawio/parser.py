"""
Excel / CSV 表格解析器
适配用户的 CRG 表格格式
"""
import pandas as pd
from pathlib import Path
from typing import List, Dict


class CrgExcelParser:
    """CRG Excel 表格解析器"""

    SUPPORTED_FORMATS = [".xlsx", ".xls", ".csv"]

    def __init__(self, file_path: str, sheet_name: str = None):
        self.file_path = Path(file_path)
        self.sheet_name = sheet_name

        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if self.file_path.suffix not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {self.file_path.suffix}")

    def parse(self) -> List[Dict]:
        """解析表格，返回字典列表"""
        df = self._read_raw()
        df = self._clean(df)
        return df.to_dict("records")

    def _read_raw(self) -> pd.DataFrame:
        """读取原始表格"""
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

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗"""
        # 统一列名（去除前后空格，转大写便于匹配）
        df.columns = [str(c).strip() for c in df.columns]

        # 必要的列映射（兼容用户表头）
        col_map = {
            "NAME": ["NAME", "name", "信号名", "时钟名称"],
            "SEL": ["SEL", "sel", "选择信号"],
            "SRC0": ["SRC0", "src0", "父时钟0", "源时钟0"],
            "SRC1": ["SRC1", "src1", "父时钟1", "源时钟1"],
            "MUX_DFLT": ["MUX_DFLT", "mux_dflt"],
            "DIV": ["DIV", "div", "分频器"],
            "DIV_WIDTH": ["DIV_WIDTH", "div_width"],
            "DIV_DFLT": ["DIV_DFLT", "div_dflt"],
            "OCC/SCAN MUX": ["OCC/SCAN MUX", "OCC", "occ", "scan mux"],
            "ICG": ["ICG", "icg"],
            "ICG_DFLT": ["ICG_DFLT", "icg_dflt"],
            "ICG_external": ["ICG_external", "icg_external", "ICG external"],
            "ICG_internal": ["ICG_internal", "icg_internal", "ICG internal"],
            "CE_DISEN": ["CE_DISEN", "ce_disen"],
            "ATTR": ["ATTR", "attr", "属性", "类型"],
        }

        rename_map = {}
        for standard, aliases in col_map.items():
            for col in df.columns:
                if col.upper() in [a.upper() for a in aliases]:
                    rename_map[col] = standard
                    break

        df = df.rename(columns=rename_map)

        # 确保 NAME 列存在
        if "NAME" not in df.columns:
            raise ValueError(
                f"Required column 'NAME' not found. Available: {list(df.columns)}"
            )

        # 去除空行（NAME 为空或 NaN 的行）
        df = df.dropna(subset=["NAME"])
        df = df[df["NAME"].astype(str).str.strip() != ""]

        # 去除分隔行（如 "Clock Generate"）
        df = df[~df["NAME"].astype(str).str.contains("Clock Generate", case=False, na=False)]

        # 去除表头重复行
        df = df[~df["NAME"].astype(str).str.upper().isin([c.upper() for c in df.columns if isinstance(c, str)])]

        # 字符串字段清洗
        str_cols = [
            "NAME", "SEL", "SRC0", "SRC1", "MUX_DFLT", "DIV",
            "DIV_WIDTH", "DIV_DFLT", "OCC/SCAN MUX", "ICG",
            "ICG_DFLT", "ICG_external", "ICG_internal", "CE_DISEN", "ATTR",
        ]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace("nan", "")
                df[col] = df[col].replace("NaN", "")
                df[col] = df[col].replace("<NA>", "")

        return df.reset_index(drop=True)

    def get_summary(self, rows: List[Dict]) -> Dict:
        attrs = {}
        for row in rows:
            attr = row.get("ATTR", "unknown").strip().lower() or "unknown"
            attrs[attr] = attrs.get(attr, 0) + 1
        return {
            "total": len(rows),
            "attrs": attrs,
        }
