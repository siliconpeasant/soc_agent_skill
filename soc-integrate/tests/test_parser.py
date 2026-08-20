from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "soc_integrate.py"
SPEC = importlib.util.spec_from_file_location("soc_integrate_cli", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class VerilogParserTest(unittest.TestCase):
    def parse(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dut.v"
            path.write_text(text)
            return MODULE.extract_modules(path)

    def test_ansi_continuation_ports(self) -> None:
        modules = self.parse(
            "module dut(input wire [7:0] a, b, output wire y); assign y = a[0]; endmodule\n"
        )
        self.assertEqual(
            modules[0].ports,
            [("input", "[7:0]", "a"), ("input", "[7:0]", "b"), ("output", "", "y")],
        )

    def test_non_ansi_ports_fail_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "ANSI-style"):
            self.parse("module dut(a, y); input a; output y; endmodule\n")

    def test_package_typed_port_requires_wrapper(self) -> None:
        with self.assertRaisesRegex(ValueError, "normalized wrapper"):
            self.parse("module dut(input pkg::word_t a, output wire y); endmodule\n")


if __name__ == "__main__":
    unittest.main()
