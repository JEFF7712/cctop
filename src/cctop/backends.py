from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .models import Calculation, Status
from .orca import looks_like_orca, parse_orca


Detector = Callable[[Path], bool]
Parser = Callable[[Path], Calculation]


@dataclass(frozen=True, slots=True)
class Backend:
    name: str
    suffixes: frozenset[str]
    filenames: frozenset[str]
    detect: Detector
    parse: Parser

    def is_candidate(self, path: Path) -> bool:
        return path.suffix.lower() in self.suffixes or path.name.lower() in self.filenames


BACKENDS = (
    Backend(
        name="ORCA",
        suffixes=frozenset({".out", ".log"}),
        filenames=frozenset(),
        detect=looks_like_orca,
        parse=parse_orca,
    ),
)


def is_supported_candidate(path: Path) -> bool:
    return any(backend.is_candidate(path) for backend in BACKENDS)


def parse_supported_file(path: Path) -> Calculation:
    for backend in BACKENDS:
        if backend.is_candidate(path) and backend.detect(path):
            return backend.parse(path)
    return Calculation(path=path, status=Status.UNKNOWN)


def supported_programs() -> list[str]:
    return [backend.name for backend in BACKENDS]
