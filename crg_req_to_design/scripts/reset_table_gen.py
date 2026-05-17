"""
复位树设计表生成器
"""
from typing import List, Dict


class ResetTreeGenerator:
    """Generate reset tree design rows from requirement signals."""

    def __init__(self, resets: List[Dict]):
        self.resets = resets
        self.root_name: str = ""

    def generate(self) -> List[Dict]:
        """Return list of design-table row dicts for reset tree."""
        rows: List[Dict] = []
        if not self.resets:
            return rows

        root_reset = None
        debug_resets = []
        subsystem_resets = []

        for r in self.resets:
            n = r["name"].lower()
            if "poreset" in n:
                root_reset = r
            elif "trst" in n or "srst" in n:
                debug_resets.append(r)
            else:
                subsystem_resets.append(r)

        if not root_reset and subsystem_resets:
            root_reset = subsystem_resets.pop(0)

        if root_reset:
            self.root_name = root_reset["name"]
            rows.append(self._make_row(name=root_reset["name"], attr="input"))

        for r in debug_resets:
            rows.append(self._make_row(name=r["name"], attr="input"))

        for r in subsystem_resets:
            rows.append(self._make_row(
                name=r["name"],
                attr="output",
                src0=self.root_name,
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
