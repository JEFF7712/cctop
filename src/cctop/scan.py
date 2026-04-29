from __future__ import annotations

import fnmatch
from pathlib import Path

from .backends import is_supported_candidate, parse_supported_file
from .models import Calculation, Status


def load_calculations(path: Path, exclude: list[str] | None = None) -> list[Calculation]:
    path = path.expanduser().resolve()
    if path.is_file():
        return [parse_file(path)]
    if path.is_dir():
        return scan_directory(path, exclude=exclude)
    raise FileNotFoundError(path)


def load_many_calculations(paths: list[Path], exclude: list[str] | None = None) -> list[Calculation]:
    calculations: list[Calculation] = []
    for path in paths:
        calculations.extend(load_calculations(path, exclude=exclude))
    return calculations


def scan_directory(root: Path, exclude: list[str] | None = None) -> list[Calculation]:
    patterns = exclude or []
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and is_supported_candidate(path)
        and not any(fnmatch.fnmatch(path.name, pat) for pat in patterns)
    ]
    calculations = [parse_file(path) for path in sorted(files)]
    return calculations


def parse_file(path: Path) -> Calculation:
    return parse_supported_file(path)


def summarize_status(calculations: list[Calculation]) -> dict[Status, int]:
    return {status: sum(1 for calc in calculations if calc.status == status) for status in Status}
