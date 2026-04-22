from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from cctop.cli import main


ORCA_DONE = """
O   R   C   A
Program Version 6.0.0
FINAL SINGLE POINT ENERGY     -1.123456789
****ORCA TERMINATED NORMALLY****
"""

QCHEM_DONE = """
Welcome to Q-Chem 6.2
Total energy in the final basis set = -1.234567890
Thank you very much for using Q-Chem.
"""


class CliTest(unittest.TestCase):
    def test_view_accepts_multiple_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "job_a").mkdir()
            (root / "job_b").mkdir()
            (root / "job_a" / "orca.out").write_text(ORCA_DONE)
            (root / "job_b" / "qchem.out").write_text(QCHEM_DONE)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main([str(root / "job_a"), str(root / "job_b")])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("2 calculations", output)
        self.assertIn("job_a/orca.out", output)
        self.assertIn("job_b/qchem.out", output)

    def test_export_accepts_multiple_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_path = root / "summary.csv"
            (root / "job_a").mkdir()
            (root / "job_b").mkdir()
            (root / "job_a" / "orca.out").write_text(ORCA_DONE)
            (root / "job_b" / "qchem.out").write_text(QCHEM_DONE)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "export",
                        str(root / "job_a"),
                        str(root / "job_b"),
                        "--output",
                        str(output_path),
                    ]
                )

            exported = output_path.read_text()

        self.assertEqual(exit_code, 0)
        self.assertIn("job_a/orca.out", exported)
        self.assertIn("job_b/qchem.out", exported)


if __name__ == "__main__":
    unittest.main()
