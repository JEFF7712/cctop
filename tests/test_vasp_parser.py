from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cctop.models import Status
from cctop.vasp import looks_like_vasp, parse_vasp


VASP_DONE_OUTCAR = """
vasp.6.4.2 18Apr2023
free  energy   TOTEN  =       -12.34567890 eV
Elapsed time (sec):  123.45
General timing and accounting informations for this job:
"""

VASP_RUNNING_OUTCAR = """
vasp.6.4.2 18Apr2023
free  energy   TOTEN  =       -8.76543210 eV
"""

VASP_SUSPICIOUS_OUTCAR = """
vasp.6.4.2 18Apr2023
free  energy   TOTEN  =       -10.00000000 eV
reached maximum number of ionic steps
General timing and accounting informations for this job:
"""


class VaspParserTest(unittest.TestCase):
    def test_done_outcar(self) -> None:
        calc, detected = self._parse("OUTCAR", VASP_DONE_OUTCAR)
        self.assertTrue(detected)
        self.assertEqual(calc.program, "VASP")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.version, "6.4.2")
        self.assertAlmostEqual(calc.final_energy or 0.0, -12.34567890)
        self.assertEqual(calc.runtime_seconds, 123)
        self.assertEqual(calc.termination, "normal")
        self.assertEqual(calc.warning_count, 0)

    def test_recent_incomplete_outcar_is_running(self) -> None:
        calc, _ = self._parse("OUTCAR", VASP_RUNNING_OUTCAR)
        self.assertEqual(calc.status, Status.RUNNING)
        self.assertAlmostEqual(calc.final_energy or 0.0, -8.76543210)
        self.assertIsNone(calc.termination)

    def test_ionic_convergence_warning_is_suspicious(self) -> None:
        calc, _ = self._parse("OUTCAR", VASP_SUSPICIOUS_OUTCAR)
        self.assertEqual(calc.status, Status.SUSPICIOUS)
        self.assertEqual(calc.warning_count, 1)
        self.assertEqual(calc.warnings[0].code, "IONIC_NOT_CONVERGED")

    def test_oszicar_final_energy_is_used_when_present(self) -> None:
        calc, detected = self._parse(
            "OSZICAR",
            """
        vasp.6.4.2 18Apr2023
        1 F= -.12345678 E0= -.12000000 d E =-.12345678
        2 F= -.23456789 E0= -.23000000 d E =-.23456789
        """,
        )
        self.assertTrue(detected)
        self.assertAlmostEqual(calc.final_energy or 0.0, -0.23456789)

    def _parse(self, filename: str, content: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / filename
            path.write_text(content)
            return parse_vasp(path), looks_like_vasp(path)


if __name__ == "__main__":
    unittest.main()
