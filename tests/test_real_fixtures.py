from __future__ import annotations

import unittest
from pathlib import Path

from cctop.models import Status
from cctop.scan import parse_file, scan_directory


FIXTURES = Path(__file__).parent / "fixtures" / "real"


class RealFixtureParserTest(unittest.TestCase):
    def test_real_gaussian_output(self) -> None:
        calc = parse_file(FIXTURES / "cclib" / "gaussian_water_hf_solvent_cpcm.log")

        self.assertEqual(calc.program, "Gaussian")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.version, "16")
        self.assertEqual(calc.method, "SP")
        self.assertEqual(calc.basis, "STO-3G")
        self.assertAlmostEqual(calc.final_energy or 0.0, -74.9667426458)
        self.assertEqual(calc.termination, "normal")

    def test_real_qchem_ir_output(self) -> None:
        calc = parse_file(FIXTURES / "cclib" / "qchem_water_ir.out")

        self.assertEqual(calc.program, "Q-Chem")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.version, "5.1")
        self.assertEqual(calc.method, "b3lyp")
        self.assertEqual(calc.basis, "sto-3g")
        self.assertAlmostEqual(calc.final_energy or 0.0, -75.3178467153)
        self.assertEqual(calc.imaginary_frequency_count, 0)
        self.assertEqual(calc.termination, "normal")

    def test_real_orca_output(self) -> None:
        calc = parse_file(FIXTURES / "cclib" / "orca_water_hf_solvent_cpcm.log")

        self.assertEqual(calc.program, "ORCA")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.version, "5.0.3")
        self.assertAlmostEqual(calc.final_energy or 0.0, -74.96766981555)
        self.assertEqual(calc.termination, "normal")

    def test_real_xtb_single_point_output(self) -> None:
        calc = parse_file(FIXTURES / "cclib" / "xtb_dvb_sp.out")

        self.assertEqual(calc.program, "xTB")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.version, "6.6.1")
        self.assertEqual(calc.method, "GFN2-xTB")
        self.assertAlmostEqual(calc.final_energy or 0.0, -26.425939358406)
        self.assertEqual(calc.termination, "normal")

    def test_real_vasp_outcar_output(self) -> None:
        calc = parse_file(FIXTURES / "pymatgen" / "vasp_static_silicon" / "OUTCAR")

        self.assertEqual(calc.program, "VASP")
        self.assertEqual(calc.status, Status.DONE)
        self.assertEqual(calc.version, "5.2.12")
        self.assertAlmostEqual(calc.final_energy or 0.0, -10.645278)
        self.assertEqual(calc.termination, "normal")

    def test_real_vasp_oszicar_output(self) -> None:
        calc = parse_file(FIXTURES / "pymatgen" / "vasp_static_silicon" / "OSZICAR")

        self.assertEqual(calc.program, "VASP")
        self.assertAlmostEqual(calc.final_energy or 0.0, -10.645278)

    def test_scan_real_fixture_tree_routes_supported_outputs(self) -> None:
        calculations = scan_directory(FIXTURES)

        programs = sorted(calc.program for calc in calculations)
        self.assertEqual(programs, ["Gaussian", "ORCA", "Q-Chem", "VASP", "VASP", "xTB"])


if __name__ == "__main__":
    unittest.main()
