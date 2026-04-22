from __future__ import annotations

import re
import time
from pathlib import Path

from .models import Calculation, Status, Warning


FLOAT_RE = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?"

FATAL_PATTERNS = [
    (
        "GAUSSIAN_ERROR_TERMINATION",
        "Gaussian error termination",
        re.compile(r"\berror termination\b", re.I),
    ),
    (
        "SCF_NOT_CONVERGED",
        "SCF did not converge",
        re.compile(r"\bSCF\s+(?:has\s+)?not\s+converged\b", re.I),
    ),
    (
        "CONVERGENCE_FAILURE",
        "Convergence failure",
        re.compile(r"\bconvergence failure\b", re.I),
    ),
]

SUSPICIOUS_PATTERNS = [
    (
        "OPTIMIZATION_NOT_CONVERGED",
        "Optimization did not converge",
        re.compile(
            r"\b(?:optimization|optimisation)\s+(?:did\s+not|has\s+not|not)\s+converge(?:d)?\b"
            r"|\boptimization\s+stopped\b",
            re.I,
        ),
    ),
]


def parse_gaussian(path: Path) -> Calculation:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    calc = Calculation(path=path, program="Gaussian")

    calc.version = _parse_version(text)

    route_line = _find_route_line(lines)
    if route_line:
        calc.method, calc.basis = _parse_method_basis(route_line)

    charge_mult = _find_charge_multiplicity(lines)
    if charge_mult:
        calc.charge, calc.multiplicity = charge_mult

    energies = [float(match) for match in re.findall(r"SCF Done:\s+E\([^)]+\)\s*=\s*(" + FLOAT_RE + r")", text, re.I)]
    if energies:
        calc.final_energy = energies[-1]

    frequencies = _parse_frequencies(lines)
    if frequencies:
        calc.lowest_frequency = min(frequencies)
        calc.imaginary_frequency_count = sum(1 for frequency in frequencies if frequency < 0.0)
    else:
        calc.imaginary_frequency_count = None

    calc.runtime_seconds = _parse_runtime_seconds(text)
    calc.termination = _parse_termination(text)
    calc.warnings.extend(_collect_warnings(lines, frequencies))
    calc.status = _classify(calc, text)
    return calc


def looks_like_gaussian(path: Path) -> bool:
    try:
        head = path.read_text(errors="replace")[:12000]
    except OSError:
        return False
    return (
        "Entering Gaussian System" in head
        or "Normal termination of Gaussian" in head
        or re.search(r"\bGaussian\s+\d+\b", head) is not None
    )


def _parse_version(text: str) -> str | None:
    patterns = [
        re.compile(r"\bGaussian\s+(\d+(?:\.\d+)?)(?:,?\s+Revision\s+([A-Za-z0-9.\-]+))?\b", re.I),
        re.compile(r"\bGaussian\s+(\d+(?:\.\d+)?):\s+([A-Za-z0-9._\-]+)", re.I),
        re.compile(r"\bRevision\s+([A-Za-z0-9.\-]+)\b", re.I),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        groups = [group for group in match.groups() if group]
        if not groups:
            continue
        if len(groups) == 1:
            return groups[0]
        if groups[0].isdigit() or re.fullmatch(r"\d+(?:\.\d+)?", groups[0]):
            return f"{groups[0]} Rev {groups[1]}"
        return " ".join(groups)
    return None


def _find_route_line(lines: list[str]) -> str | None:
    for line in lines[:1000]:
        if line.lstrip().startswith("#"):
            return line.strip()
    return None


def _parse_method_basis(route_line: str) -> tuple[str | None, str | None]:
    cleaned = route_line.lstrip("#").strip()
    tokens = [token.strip() for token in cleaned.split() if token.strip()]
    method = None
    basis = None

    for token in tokens:
        lowered = token.lower().strip(",")
        if lowered in {"p", "n", "t", "u", "d", "h"}:
            continue
        if "(" in token and "/" in token and token.lower().startswith("iop("):
            continue
        if "/" in token:
            left, right = token.split("/", 1)
            if method is None and left and re.search(r"[A-Za-z]", left):
                method = left.strip()
            if basis is None and right:
                basis = right.strip()
            continue
        if method is None and lowered not in {"opt", "freq", "scf", "geom", "guess", "scrf"}:
            method = token

    return method, basis


def _find_charge_multiplicity(lines: list[str]) -> tuple[int, int] | None:
    patterns = [
        re.compile(r"^\s*Charge\s*=\s*(-?\d+)\s+Multiplicity\s*=\s*(\d+)\s*$", re.I),
        re.compile(r"^\s*Charge\s+(-?\d+)\s+Multiplicity\s+(\d+)\s*$", re.I),
    ]
    for line in lines:
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                return int(match.group(1)), int(match.group(2))
    return None


def _parse_frequencies(lines: list[str]) -> list[float]:
    latest_frequencies: list[float] = []
    pattern = re.compile(r"^\s*Frequencies\s*--\s*(.+)$", re.I)
    for line in lines:
        match = pattern.search(line)
        if not match:
            continue
        latest_frequencies = [float(value) for value in re.findall(FLOAT_RE, match.group(1))]
    return latest_frequencies


def _parse_runtime_seconds(text: str) -> int | None:
    patterns = [
        re.compile(
            r"\bJob cpu time:\s*(\d+)\s+days\s+(\d+)\s+hours\s+(\d+)\s+minutes\s+(" + FLOAT_RE + r")\s+seconds",
            re.I,
        ),
        re.compile(
            r"\bElapsed time:\s*(\d+)\s+days\s+(\d+)\s+hours\s+(\d+)\s+minutes\s+(" + FLOAT_RE + r")\s+seconds",
            re.I,
        ),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        days, hours, minutes = (int(part) for part in match.groups()[:3])
        seconds = int(float(match.group(4)))
        return (((days * 24) + hours) * 60 + minutes) * 60 + seconds
    return None


def _parse_termination(text: str) -> str | None:
    if re.search(r"\bNormal termination of Gaussian\b", text, re.I):
        return "normal"
    if re.search(r"\berror termination\b", text, re.I):
        return "error"
    return None


def _collect_warnings(lines: list[str], frequencies: list[float]) -> list[Warning]:
    warnings: list[Warning] = []
    for index, line in enumerate(lines, start=1):
        for code, message, pattern in FATAL_PATTERNS + SUSPICIOUS_PATTERNS:
            if pattern.search(line):
                warnings.append(Warning(code=code, message=message, line=index))
                break

    if frequencies:
        imaginary_count = sum(1 for frequency in frequencies if frequency < 0.0)
        if imaginary_count:
            warnings.append(
                Warning(
                    code="IMAGINARY_FREQUENCIES",
                    message=f"{imaginary_count} imaginary frequency value(s) found",
                    line=None,
                )
            )

    return _dedupe_warnings(warnings)


def _dedupe_warnings(warnings: list[Warning]) -> list[Warning]:
    seen: set[tuple[str, int | None]] = set()
    unique: list[Warning] = []
    for warning in warnings:
        key = (warning.code, warning.line)
        if key in seen:
            continue
        seen.add(key)
        unique.append(warning)
    return unique


def _classify(calc: Calculation, text: str) -> Status:
    fatal_codes = {"GAUSSIAN_ERROR_TERMINATION", "SCF_NOT_CONVERGED", "CONVERGENCE_FAILURE"}
    if any(warning.code in fatal_codes for warning in calc.warnings):
        return Status.FAILED
    if calc.termination == "normal":
        if calc.warnings:
            return Status.SUSPICIOUS
        return Status.DONE
    if _looks_recent(calc.path) and "Normal termination of Gaussian" not in text:
        return Status.RUNNING
    if any(warning.code == "OPTIMIZATION_NOT_CONVERGED" for warning in calc.warnings):
        return Status.SUSPICIOUS
    if any(warning.code == "IMAGINARY_FREQUENCIES" for warning in calc.warnings):
        return Status.SUSPICIOUS
    return Status.UNKNOWN


def _looks_recent(path: Path) -> bool:
    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age_seconds < 2 * 60 * 60
