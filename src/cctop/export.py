from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Calculation, EXPORT_FIELDS


def export_calculations(
    calculations: list[Calculation],
    output_path: Path,
    export_format: str,
    root: Path | None = None,
) -> None:
    export_format = export_format.lower()
    if export_format == "csv":
        _export_csv(calculations, output_path, root)
        return
    if export_format == "json":
        _export_json(calculations, output_path, root)
        return
    raise ValueError(f"Unsupported export format: {export_format}")


def _export_csv(calculations: list[Calculation], output_path: Path, root: Path | None) -> None:
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for calc in calculations:
            record = calc.to_record(root=root)
            writer.writerow({field: record.get(field) for field in EXPORT_FIELDS})


def _export_json(calculations: list[Calculation], output_path: Path, root: Path | None) -> None:
    records = [calc.to_record(root=root) for calc in calculations]
    output_path.write_text(json.dumps(records, indent=2) + "\n")
