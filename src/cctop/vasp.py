from __future__ import annotations

import re
import time
from pathlib import Path

from .models import Calculation, Status, Warning


FLOAT_RE = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?"

FATAL_PATTERNS = [
    (
        "VASP_ERROR",
        "VASP reported an error termination",
        re.compile(r"\berror termination\b|\bfatal error\b|\binternal error\b", re.I),
    ),
    (
        "SCF_DIVERGED",
        "Electronic self-consistency did not converge",
        re.compile(r"\bself-?consistency\b.*\bnot\s+converged\b", re.I),
    ),
]

SUSPICIOUS_PATTERNS = [
    (
        "IONIC_NOT_CONVERGED",
        "Ionic convergence was not reached",
        re.compile(
            r"reached\s+maximum\s+number\s+of\s+ionic\s+steps"
            r"|ionic\s+convergence\s+not\s+reached"
            r"|structural\s+energy\s+minimisation\s+did\s+not\s+converge",
            re.I,
        ),
    ),
    (
        "ELECTRONIC_NOT_CONVERGED",
        "Electronic convergence was not reached",
        re.compile(
            r"reached\s+maximum\s+number\s+of\s+electronic\s+steps"
            r"|electronic\s+convergence\s+not\s+reached"
            r"|self-?consistency\s+cycle\s+not\s+converged",
            re.I,
        ),
    ),
]


def parse_vasp(path: Path) -> Calculation:
    text = path.read_text(errors="replace")
    if not looks_like_vasp(path):
        return Calculation(path=path)

    lines = text.splitlines()
    calc = Calculation(path=path, program="VASP")
    calc.version = _parse_version(text)
    calc.final_energy = _parse_final_energy(lines)
    calc.runtime_seconds = _parse_runtime_seconds(text)
    calc.termination = _parse_termination(text)
    calc.warnings.extend(_collect_warnings(text))
    calc.status = _classify(calc, text)
    return calc


def looks_like_vasp(path: Path) -> bool:
    try:
        head = path.read_text(errors="replace")[:8000]
    except OSError:
        return False

    name = path.name.lower()
    if name == "outcar":
        return bool(
            re.search(r"\bvasp\.\s*[^\s]+", head, re.I)
            or re.search(r"free\s+energy\s+TOTEN", head, re.I)
            or "general timing and accounting informations for this job" in head.lower()
        )
    if name == "oszicar":
        return bool(re.search(r"\bF=\s*" + FLOAT_RE, head) or re.search(r"\bE0=\s*" + FLOAT_RE, head))

    return bool(
        re.search(r"\bvasp\.\s*[^\s]+", head, re.I)
        or re.search(r"free\s+energy\s+TOTEN", head, re.I)
    )


def _parse_version(text: str) -> str | None:
    match = re.search(r"\bvasp\.\s*([^\s]+)", text, re.I)
    return match.group(1) if match else None


def _parse_final_energy(lines: list[str]) -> float | None:
    outcar_energies: list[float] = []
    oszicar_energies: list[float] = []

    for line in lines:
        match = re.search(r"free\s+energy\s+TOTEN\s*=\s*(" + FLOAT_RE + r")\s+eV", line, re.I)
        if match:
            outcar_energies.append(float(match.group(1)))
            continue

        match = re.search(r"\bF=\s*(" + FLOAT_RE + r")", line)
        if match:
            oszicar_energies.append(float(match.group(1)))
            continue

        match = re.search(r"\bE0=\s*(" + FLOAT_RE + r")", line)
        if match:
            oszicar_energies.append(float(match.group(1)))

    if outcar_energies:
        return outcar_energies[-1]
    if oszicar_energies:
        return oszicar_energies[-1]
    return None


def _parse_runtime_seconds(text: str) -> int | None:
    match = re.search(r"Elapsed time \(sec\):\s*(" + FLOAT_RE + r")", text, re.I)
    if match:
        return int(round(float(match.group(1))))

    match = re.search(r"Total CPU time used \(sec\):\s*(" + FLOAT_RE + r")", text, re.I)
    if match:
        return int(round(float(match.group(1))))

    return None


def _parse_termination(text: str) -> str | None:
    if re.search(r"General timing and accounting informations for this job:", text, re.I):
        return "normal"
    return None


def _collect_warnings(text: str) -> list[Warning]:
    warnings: list[Warning] = []
    for code, message, pattern in FATAL_PATTERNS + SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            warnings.append(Warning(code=code, message=message, line=None))
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
    fatal_codes = {"VASP_ERROR", "SCF_DIVERGED"}
    if any(warning.code in fatal_codes for warning in calc.warnings):
        return Status.FAILED
    if calc.termination == "normal":
        if calc.warnings:
            return Status.SUSPICIOUS
        return Status.DONE
    if _looks_recent(calc.path) and not calc.warnings:
        return Status.RUNNING
    if calc.warnings:
        return Status.SUSPICIOUS
    return Status.UNKNOWN


def _looks_recent(path: Path) -> bool:
    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age_seconds < 2 * 60 * 60
