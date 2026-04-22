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


class BackendRegistryTest(unittest.TestCase):
    def test_supported_programs_lists_orca(self) -> None:
        self.assertEqual(supported_programs(), ["ORCA"])

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


if __name__ == "__main__":
    unittest.main()
