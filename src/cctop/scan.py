from __future__ import annotations

from pathlib import Path

from .models import Calculation, Status
from .orca import looks_like_orca, parse_orca

OUTPUT_SUFFIXES = {".out", ".log"}


def load_calculations(path: Path) -> list[Calculation]:
    path = path.expanduser().resolve()
    if path.is_file():
        return [parse_file(path)]
    if path.is_dir():
        return scan_directory(path)
    raise FileNotFoundError(path)


def scan_directory(root: Path) -> list[Calculation]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in OUTPUT_SUFFIXES
    ]
    calculations = [parse_file(path) for path in sorted(files)]
    return calculations


def parse_file(path: Path) -> Calculation:
    if looks_like_orca(path):
        return parse_orca(path)
    return Calculation(path=path, status=Status.UNKNOWN)


def summarize_status(calculations: list[Calculation]) -> dict[Status, int]:
    return {status: sum(1 for calc in calculations if calc.status == status) for status in Status}
