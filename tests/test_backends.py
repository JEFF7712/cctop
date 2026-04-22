from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cctop.backends import supported_programs
from cctop.models import Status
from cctop.scan import parse_file, scan_directory


ORCA_DONE = """
O   R   C   A
Program Version 6.0.0
! B3LYP def2-SVP
* xyz 0 1
H 0 0 0
H 0 0 1
*
FINAL SINGLE POINT ENERGY     -1.123456789
****ORCA TERMINATED NORMALLY****
"""

VASP_DONE = """
vasp.6.4.2 18Apr2023
free  energy   TOTEN  =       -12.34567890 eV
General timing and accounting informations for this job:
"""

GAUSSIAN_DONE = """
Entering Gaussian System, Link 0=g16
Gaussian 16, Revision C.01
#p b3lyp/6-31g(d) sp
Charge = 0 Multiplicity = 1
SCF Done:  E(RB3LYP) =  -100.123456789 A.U. after 8 cycles
Normal termination of Gaussian 16
"""

QCHEM_DONE = """
Welcome to Q-Chem 6.2
$rem
METHOD B3LYP
BASIS def2-SVP
$end
Total energy in the final basis set = -1.234567890
Thank you very much for using Q-Chem.
"""

XTB_DONE = """
* xtb version 6.7.1
|  GFN2-xTB
TOTAL ENERGY       -12.34567890 Eh
normal termination
"""


class BackendRegistryTest(unittest.TestCase):
    def test_supported_programs_lists_registered_backends(self) -> None:
        self.assertEqual(supported_programs(), ["ORCA", "VASP", "Gaussian", "Q-Chem", "xTB/CREST"])

    def test_parse_file_uses_registered_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orca.out"
            path.write_text(ORCA_DONE)

            calc = parse_file(path)

        self.assertEqual(calc.program, "ORCA")
        self.assertEqual(calc.status, Status.DONE)

    def test_scan_ignores_non_candidate_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text("not an output file")
            (root / "orca.out").write_text(ORCA_DONE)

            calculations = scan_directory(root)

        self.assertEqual(len(calculations), 1)
        self.assertEqual(calculations[0].program, "ORCA")

    def test_scan_routes_registered_backend_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "orca.out").write_text(ORCA_DONE)
            (root / "OUTCAR").write_text(VASP_DONE)
            (root / "gaussian.log").write_text(GAUSSIAN_DONE)
            (root / "qchem.out").write_text(QCHEM_DONE)
            (root / "xtb.out").write_text(XTB_DONE)

            calculations = scan_directory(root)

        programs = sorted(calc.program for calc in calculations)
        self.assertEqual(programs, ["Gaussian", "ORCA", "Q-Chem", "VASP", "xTB"])


if __name__ == "__main__":
    unittest.main()
