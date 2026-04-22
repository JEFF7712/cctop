from __future__ import annotations

import re
import time
from pathlib import Path

from .models import Calculation, Status, Warning


FLOAT_RE = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?"

FATAL_PATTERNS = [
    (
        "QCHEM_ERROR",
        "Q-Chem error termination",
        re.compile(r"\b(error termination|fatal error|aborting the run|job crashed)\b", re.I),
    ),
    (
        "SCF_NOT_CONVERGED",
        "SCF did not converge",
        re.compile(r"\bSCF\b.*\b(?:did not converge|failed to converge|not converged)\b", re.I),
    ),
]

SUSPICIOUS_PATTERNS = [
    (
        "OPT_NOT_CONVERGED",
        "Optimization did not converge",
        re.compile(
            r"\b(?:geometry\s+)?optimization\b.*\b(?:did not converge|failed to converge|not converged|stopped)\b",
            re.I,
        ),
    ),
]


def parse_qchem(path: Path) -> Calculation:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    calc = Calculation(path=path, program="Q-Chem")

    calc.version = _first_match(
        text,
        r"\bQ-?Chem(?:\s+version)?\s+([0-9][^\s,)]*)",
    )

    rem_lines = _find_block(lines, "$rem")
    if rem_lines:
        calc.method, calc.basis = _parse_method_basis(rem_lines)

    molecule_line = _find_molecule_charge_multiplicity(lines)
    if molecule_line:
        calc.charge, calc.multiplicity = molecule_line

    energies = [
        float(match)
        for match in re.findall(
            r"Total energy in the final basis set\s*=\s*(" + FLOAT_RE + r")",
            text,
            re.I,
        )
    ]
    if not energies:
        energies = [
            float(match)
            for match in re.findall(
                r"Total energy\s*=\s*(" + FLOAT_RE + r")",
                text,
                re.I,
            )
        ]
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


def looks_like_qchem(path: Path) -> bool:
    try:
        head = path.read_text(errors="replace")[:8000]
    except OSError:
        return False

    lowered = head.lower()
    return (
        "q-chem" in lowered
        or "$molecule" in lowered and "$rem" in lowered
        or "thank you very much for using q-chem" in lowered
    )


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.I)
    return match.group(1) if match else None


def _find_block(lines: list[str], marker: str) -> list[str]:
    in_block = False
    block: list[str] = []
    marker_lower = marker.lower()
    for line in lines:
        stripped = line.strip().lower()
        if stripped == marker_lower:
            in_block = True
            continue
        if in_block and stripped == "$end":
            return block
        if in_block:
            block.append(line)
    return block


def _parse_method_basis(lines: list[str]) -> tuple[str | None, str | None]:
    method = None
    basis = None
    for line in lines:
        match = re.match(r"^\s*(METHOD|BASIS|EXCHANGE)\s*(?:=|\s)\s*(.+?)\s*$", line, re.I)
        if not match:
            continue
        key = match.group(1).upper()
        value = match.group(2).strip()
        if key in {"METHOD", "EXCHANGE"} and method is None:
            method = value.split()[0]
        elif key == "BASIS" and basis is None:
            basis = value.split()[0]
    return method, basis


def _find_molecule_charge_multiplicity(lines: list[str]) -> tuple[int, int] | None:
    in_molecule = False
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered == "$molecule":
            in_molecule = True
            continue
        if in_molecule and lowered == "$end":
            break
        if in_molecule:
            match = re.match(r"^\s*(-?\d+)\s+(\d+)\s*$", line)
            if match:
                return int(match.group(1)), int(match.group(2))
    return None


def _parse_frequencies(lines: list[str]) -> list[float]:
    latest_frequencies: list[float] = []
    current_frequencies: list[float] = []
    in_block = False
    for line in lines:
        if re.search(r"\bVIBRATIONAL ANALYSIS\b", line, re.I):
            if in_block:
                latest_frequencies = current_frequencies
            current_frequencies = []
            in_block = True
            continue
        if not in_block:
            continue

        match = re.search(r"\bFrequenc(?:y|ies)\b\s*[:=]\s*(.+)$", line, re.I)
        if match:
            current_frequencies.extend(float(value) for value in re.findall(FLOAT_RE, match.group(1)))

    if in_block:
        latest_frequencies = current_frequencies
    return latest_frequencies


def _parse_runtime_seconds(text: str) -> int | None:
    match = re.search(
        r"Total job time:\s*(\d+)\s+days\s+(\d+)\s+hours\s+(\d+)\s+minutes\s+(\d+)\s+seconds",
        text,
        re.I,
    )
    if not match:
        return None
    days, hours, minutes, seconds = (int(part) for part in match.groups())
    return (((days * 24) + hours) * 60 + minutes) * 60 + seconds


def _parse_termination(text: str) -> str | None:
    if re.search(r"Thank you very much for using Q-?Chem", text, re.I):
        return "normal"
    if re.search(r"\b(error termination|fatal error|job crashed)\b", text, re.I):
        return "error"
    return None


def _collect_warnings(lines: list[str], frequencies: list[float]) -> list[Warning]:
    warnings: list[Warning] = []

    for index, line in enumerate(lines, start=1):
        for code, message, pattern in FATAL_PATTERNS + SUSPICIOUS_PATTERNS:
            if pattern.search(line):
                warnings.append(Warning(code=code, message=message, line=index))
                break

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
    fatal_codes = {"QCHEM_ERROR", "ERROR", "SCF_NOT_CONVERGED"}
    if any(warning.code in fatal_codes for warning in calc.warnings):
        return Status.FAILED

    if calc.termination == "normal":
        if calc.warnings:
            return Status.SUSPICIOUS
        return Status.DONE

    if _looks_recent(calc.path) and "Thank you very much for using Q-Chem" not in text:
        return Status.RUNNING

    if any(warning.code == "OPT_NOT_CONVERGED" for warning in calc.warnings):
        return Status.SUSPICIOUS

    return Status.UNKNOWN


def _looks_recent(path: Path) -> bool:
    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age_seconds < 2 * 60 * 60
