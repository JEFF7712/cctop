from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from cctop.export import export_calculations
from cctop.models import Calculation, Status


class ExportTest(unittest.TestCase):
    def test_csv_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calc = Calculation(path=root / "orca.out", program="ORCA", status=Status.DONE, final_energy=-1.0)
            output = root / "summary.csv"
            export_calculations([calc], output, "csv", root=root)

            with output.open() as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(rows[0]["path"], "orca.out")
            self.assertEqual(rows[0]["status"], "DONE")
            self.assertEqual(rows[0]["final_energy"], "-1.0")


if __name__ == "__main__":
    unittest.main()
