from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cctop.models import Status
from cctop.xtb import looks_like_xtb, parse_xtb


XTB_DONE = """
* xtb version 6.7.1
|  program call: xtb molecule.xyz --gfn 2 --opt
|  GFN2-xTB
TOTAL ENERGY       -12.34567890 Eh
wall time : 0 d 0 h 2 m 3 s
normal termination
"""

XTB_IMAGINARY = """
* xtb version 6.7.1
|  GFN2-xTB
TOTAL ENERGY       -12.34567890 Eh
imaginary frequency : -54.3 cm-1
normal termination
"""

XTB_FAILED = """
* xtb version 6.7.1
|  GFN2-xTB
SCC not converged after 250 cycles
geometry optimization did not converge
abnormal termination
"""

XTB_RUNNING = """
* xtb version 6.7.1
|  GFN2-xTB
TOTAL ENERGY       -12.34567890 Eh
"""

CREST_DONE = """
CREST version 3.0.2
|  metadynamics search
TOTAL ENERGY       -8.76543210 Eh
elapsed time : 0 h 1 m 4 s
CREST terminated normally
"""


class XtbParserTest(unittest.TestCase):
    def test_done_output(self) -> None:
        calc = self._parse(XTB_DONE, filename="xtb.out")
        self.assertEqual(calc.program, "xTB")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.version, "6.7.1")
        self.assertEqual(calc.method, "GFN2-xTB")
        self.assertAlmostEqual(calc.final_energy or 0.0, -12.3456789)
        self.assertEqual(calc.runtime_seconds, 123)

    def test_imaginary_frequency_is_suspicious(self) -> None:
        calc = self._parse(XTB_IMAGINARY, filename="xtb.out")
        self.assertEqual(calc.status, Status.SUSPICIOUS)
        self.assertEqual(calc.imaginary_frequency_count, 1)
        self.assertAlmostEqual(calc.lowest_frequency or 0.0, -54.3)

    def test_failed_output(self) -> None:
        calc = self._parse(XTB_FAILED, filename="xtb.out")
        self.assertEqual(calc.status, Status.FAILED)
        self.assertGreaterEqual(calc.warning_count, 2)

    def test_recent_incomplete_output_is_running(self) -> None:
        calc = self._parse(XTB_RUNNING, filename="xtb.out")
        self.assertEqual(calc.status, Status.RUNNING)

    def test_crest_detection(self) -> None:
        calc = self._parse(CREST_DONE, filename="crest.out")
        self.assertEqual(calc.program, "CREST")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.method, "CREST")
        self.assertEqual(calc.runtime_seconds, 64)

    def test_detection_helper_matches_xtb_and_crest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xtb_path = Path(tmp) / "xtb.out"
            crest_path = Path(tmp) / "crest.out"
            xtb_path.write_text(XTB_DONE)
            crest_path.write_text(CREST_DONE)
            self.assertTrue(looks_like_xtb(xtb_path))
            self.assertTrue(looks_like_xtb(crest_path))

    def _parse(self, content: str, filename: str) -> object:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / filename
            path.write_text(content)
            return parse_xtb(path)


if __name__ == "__main__":
    unittest.main()
