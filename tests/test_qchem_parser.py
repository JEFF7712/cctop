from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from cctop.models import Status
from cctop.qchem import looks_like_qchem, parse_qchem


QCHEM_DONE = """
Welcome to Q-Chem 6.2

$molecule
0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
$end

$rem
JOBTYPE sp
METHOD B3LYP
BASIS def2-SVP
$end

SCF converged
Total energy in the final basis set = -1.234567890
Total job time: 0 days 1 hours 2 minutes 3 seconds
Thank you very much for using Q-Chem.  Have a nice day.
"""

QCHEM_FAIL = """
Welcome to Q-Chem 6.2

$molecule
0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
$end

SCF failed to converge after 200 cycles
Error termination requested by Q-Chem
"""

QCHEM_RUNNING = """
Welcome to Q-Chem 6.2

$molecule
0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
$end

$rem
JOBTYPE opt
METHOD B3LYP
BASIS 6-31G*
$end

Geometry optimization in progress
"""

QCHEM_IMAG = """
Welcome to Q-Chem 6.2

$molecule
0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
$end

$rem
JOBTYPE freq
METHOD B3LYP
BASIS def2-SVP
$end

VIBRATIONAL ANALYSIS
Frequency:   -123.45   56.78   112.34

Total energy in the final basis set = -1.222222222
Thank you very much for using Q-Chem.
"""


class QChemParserTest(unittest.TestCase):
    def test_done_single_point(self) -> None:
        calc = self._parse(QCHEM_DONE)
        self.assertEqual(calc.program, "Q-Chem")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.version, "6.2")
        self.assertEqual(calc.method, "B3LYP")
        self.assertEqual(calc.basis, "def2-SVP")
        self.assertEqual(calc.charge, 0)
        self.assertEqual(calc.multiplicity, 1)
        self.assertAlmostEqual(calc.final_energy or 0.0, -1.234567890)
        self.assertEqual(calc.runtime_seconds, 3723)
        self.assertEqual(calc.warning_count, 0)

    def test_failed_scf_is_failed(self) -> None:
        calc = self._parse(QCHEM_FAIL)
        self.assertEqual(calc.status, Status.FAILED)
        self.assertGreaterEqual(calc.warning_count, 2)

    def test_recent_incomplete_output_is_running(self) -> None:
        calc = self._parse(QCHEM_RUNNING, touch_recent=True)
        self.assertEqual(calc.status, Status.RUNNING)

    def test_imaginary_frequency_is_suspicious(self) -> None:
        calc = self._parse(QCHEM_IMAG)
        self.assertEqual(calc.status, Status.SUSPICIOUS)
        self.assertEqual(calc.imaginary_frequency_count, 1)
        self.assertAlmostEqual(calc.lowest_frequency or 0.0, -123.45)

    def test_detection_is_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("nothing to see here")
            self.assertFalse(looks_like_qchem(path))

    def _parse(self, content: str, touch_recent: bool = False):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qchem.out"
            path.write_text(content)
            if touch_recent:
                os.utime(path, None)
            return parse_qchem(path)


if __name__ == "__main__":
    unittest.main()
