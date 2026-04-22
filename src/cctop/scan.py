from __future__ import annotations

from pathlib import Path

from .backends import is_supported_candidate, parse_supported_file
from .models import Calculation, Status


def load_calculations(path: Path) -> list[Calculation]:
    path = path.expanduser().resolve()
    if path.is_file():
        return [parse_file(path)]
    if path.is_dir():
        return scan_directory(path)
    raise FileNotFoundError(path)


def load_many_calculations(paths: list[Path]) -> list[Calculation]:
    calculations: list[Calculation] = []
    for path in paths:
        calculations.extend(load_calculations(path))
    return calculations


def scan_directory(root: Path) -> list[Calculation]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and is_supported_candidate(path)
    ]
    calculations = [parse_file(path) for path in sorted(files)]
    return calculations


def parse_file(path: Path) -> Calculation:
    return parse_supported_file(path)


def summarize_status(calculations: list[Calculation]) -> dict[Status, int]:
    return {status: sum(1 for calc in calculations if calc.status == status) for status in Status}
