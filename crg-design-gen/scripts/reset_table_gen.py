"""
复位树设计表生成器
支持根据备注自动推断 SOFT、WDT、电源等复位源。
"""
from typing import List, Dict


class ResetTreeGenerator:
    """Generate reset tree design rows from requirement signals."""

    def __init__(self, resets: List[Dict]):
        self.resets = resets
        self.root_name: str = ""

    @staticmethod
    def _is_soft_reset(note: str) -> bool:
        n = note.lower()
        return "软件" in n or "soft" in n or "soft_reset" in n

    @staticmethod
    def _is_wdt_reset(note: str) -> bool:
        n = note.lower()
        return "看门狗" in n or "wdt" in n or "watchdog" in n

    @staticmethod
    def _is_power_reset(note: str) -> bool:
        n = note.lower()
        return "电源" in n or "pwrdn" in n or "power" in n or "下电" in n

    @staticmethod
    def _is_source_signal(name: str, note: str) -> bool:
        """Heuristic: is this signal a reset source rather than a target?"""
        n = note.lower()
        name_lower = name.lower()
        # Dedicated reset sources by naming convention
        source_keywords = (
            "_soft_rst_", "_wdt_rst_", "_pwrdn_rst_", "_phy_rst_",
            "_puf_rst_", "_dac_rst_", "_adc_rst_", "_enc_rst_",
            "_link_rst_", "_ep_rst_", "_hub_rst_", "_l2_rst_",
        )
        if any(kw in name_lower for kw in source_keywords):
            return True
        return (
            "复位源" in n
            or "复位控制" in n
            or "专用复位" in n
            or n.startswith("外部")
            or "external" in n
        )

    def generate(self) -> List[Dict]:
        """Return list of design-table row dicts for reset tree."""
        rows: List[Dict] = []
        if not self.resets:
            return rows

        root_reset = None
        debug_resets = []
        subsystem_resets = []
        source_resets = []  # 独立的复位源（如电源下电、看门狗）

        for r in self.resets:
            n = r["name"].lower()
            note = r.get("note", "")

            if "poreset" in n:
                root_reset = r
            elif "trst" in n or "srst" in n:
                debug_resets.append(r)
            elif self._is_power_reset(note) or self._is_source_signal(n, note):
                source_resets.append(r)
            else:
                subsystem_resets.append(r)

        if not root_reset and subsystem_resets:
            root_reset = subsystem_resets.pop(0)
        if not root_reset and source_resets:
            root_reset = source_resets.pop(0)

        if root_reset:
            self.root_name = root_reset["name"]
            rows.append(self._make_row(name=root_reset["name"], attr="input"))

        for r in debug_resets:
            rows.append(self._make_row(name=r["name"], attr="input"))

        # 独立的复位源（如电源下电复位）作为 input，后续可能被子系统引用
        for r in source_resets:
            rows.append(self._make_row(name=r["name"], attr="input"))

        # 子系统复位：根据备注推断额外输入源
        for r in subsystem_resets:
            note = r.get("note", "")
            src0 = self.root_name
            src1 = ""
            src2 = ""
            src3 = ""
            soft_dflt = ""

            # 如果备注提到软件复位，添加 SOFT 输入
            if self._is_soft_reset(note):
                src1 = "SOFT"
                soft_dflt = "N"

            # 如果备注提到看门狗，添加 WDT 输入
            if self._is_wdt_reset(note):
                # 找到看门狗复位源（如果在 source_resets 中）
                wdt_source = next(
                    (s["name"] for s in source_resets if self._is_wdt_reset(s.get("note", ""))),
                    "WDT_RST"
                )
                if not src1:
                    src1 = wdt_source
                elif not src2:
                    src2 = wdt_source
                else:
                    src3 = wdt_source

            # 自动关联同子系统的其他专用复位源
            subsystem = r.get("subsystem", "")
            extra_sources = []
            if subsystem:
                for s in source_resets:
                    if s is r:
                        continue
                    if s.get("subsystem", "") == subsystem:
                        extra_sources.append(s["name"])

            # 分配 SRC 槽位：SOFT 优先占 SRC1，专用源依次填充剩余槽位
            slots = [src1, src2, src3]
            slot_idx = 0
            # 如果已经有 SOFT，从下一个槽位开始填专用源
            while slot_idx < len(slots) and slots[slot_idx]:
                slot_idx += 1
            for src in extra_sources:
                if slot_idx < len(slots):
                    slots[slot_idx] = src
                    slot_idx += 1

            src1, src2, src3 = slots

            rows.append(self._make_row(
                name=r["name"],
                attr="output",
                src0=src0,
                src1=src1,
                src2=src2,
                src3=src3,
                soft_dflt=soft_dflt,
            ))

        return rows

    @staticmethod
    def _make_row(
        name: str,
        attr: str = "",
        src0: str = "",
        src1: str = "",
        src2: str = "",
        src3: str = "",
        soft_dflt: str = "",
    ) -> Dict:
        # Column order matches cr_tree_diag_gen example template:
        # NAME, SOFT_DFLT, SRC0, SRC1, SRC2, SRC3, ATTR
        return {
            "NAME": name,
            "SOFT_DFLT": soft_dflt,
            "SRC0": src0,
            "SRC1": src1,
            "SRC2": src2,
            "SRC3": src3,
            "ATTR": attr,
        }
