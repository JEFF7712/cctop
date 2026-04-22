from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cctop.gaussian import parse_gaussian
from cctop.models import Status


GAUSSIAN_DONE = """
 Entering Gaussian System, Link 0=g16
 Gaussian 16, Revision C.01

 #p b3lyp/6-31g(d) opt freq

 Charge = 0 Multiplicity = 1

 SCF Done:  E(RB3LYP) =  -100.123456789     A.U. after   8 cycles
 SCF Done:  E(RB3LYP) =  -101.234567890     A.U. after   9 cycles

 Frequencies --  -42.12  100.00  200.00
 Frequencies --   128.55  245.33  361.44

 Job cpu time:  0 days  1 hours  2 minutes  3.4 seconds.
 Normal termination of Gaussian 16 at Mon Jan 1 00:00:00 2026.
"""

GAUSSIAN_IMAG = """
 Entering Gaussian System, Link 0=g16
 Gaussian 16, Revision C.01
 #p b3lyp/6-31g(d) opt freq
 Charge = 0 Multiplicity = 1
 SCF Done:  E(RB3LYP) =  -75.000000000     A.U. after   8 cycles
 Frequencies --  -123.45  50.00  75.00
 Normal termination of Gaussian 16 at Mon Jan 1 00:00:00 2026.
"""

GAUSSIAN_FAIL = """
 Entering Gaussian System, Link 0=g16
 Gaussian 16, Revision C.01
 #p b3lyp/6-31g(d) opt freq
 Charge = 0 Multiplicity = 1
 SCF Done:  E(RB3LYP) =  -75.000000000     A.U. after   8 cycles
 Convergence failure -- run terminated.
 Error termination request processed by link 9999.
"""

GAUSSIAN_RUNNING = """
 Entering Gaussian System, Link 0=g16
 Gaussian 16, Revision C.01
 #p b3lyp/6-31g(d) opt freq
 Charge = 0 Multiplicity = 1
 SCF Done:  E(RB3LYP) =  -75.000000000     A.U. after   8 cycles
"""


class GaussianParserTest(unittest.TestCase):
    def test_done_output_uses_latest_energy_and_frequency_block(self) -> None:
        calc = self._parse(GAUSSIAN_DONE)
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.program, "Gaussian")
        self.assertEqual(calc.version, "16 Rev C.01")
        self.assertEqual(calc.method, "b3lyp")
        self.assertEqual(calc.basis, "6-31g(d)")
        self.assertEqual(calc.charge, 0)
        self.assertEqual(calc.multiplicity, 1)
        self.assertAlmostEqual(calc.final_energy or 0.0, -101.23456789)
        self.assertEqual(calc.imaginary_frequency_count, 0)
        self.assertAlmostEqual(calc.lowest_frequency or 0.0, 128.55)
        self.assertEqual(calc.runtime_seconds, 3723)
        self.assertEqual(calc.termination, "normal")

    def test_imaginary_frequency_is_suspicious(self) -> None:
        calc = self._parse(GAUSSIAN_IMAG)
        self.assertEqual(calc.status, Status.SUSPICIOUS)
        self.assertEqual(calc.imaginary_frequency_count, 1)
        self.assertAlmostEqual(calc.lowest_frequency or 0.0, -123.45)

    def test_error_termination_is_failed(self) -> None:
        calc = self._parse(GAUSSIAN_FAIL)
        self.assertEqual(calc.status, Status.FAILED)
        self.assertGreaterEqual(calc.warning_count, 2)
        self.assertEqual(calc.termination, "error")

    def test_recent_incomplete_output_is_running(self) -> None:
        calc = self._parse(GAUSSIAN_RUNNING)
        self.assertEqual(calc.status, Status.RUNNING)

    def _parse(self, content: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gaussian.log"
            path.write_text(content)
            return parse_gaussian(path)


if __name__ == "__main__":
    unittest.main()
