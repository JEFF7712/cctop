from __future__ import annotations

import re
import time
from pathlib import Path

from .models import Calculation, Status, Warning


FLOAT_RE = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?"

FATAL_PATTERNS = [
    ("ABNORMAL_TERMINATION", "xTB or CREST terminated abnormally", re.compile(r"\babnormal termination\b", re.I)),
    ("FATAL_ERROR", "Fatal error reported", re.compile(r"\bfatal error\b", re.I)),
    ("SCF_NOT_CONVERGED", "SCC/SCF did not converge", re.compile(r"\b(?:scc|scf)\s+not\s+converged\b", re.I)),
    ("GEOM_NOT_CONVERGED", "Geometry optimization did not converge", re.compile(r"\b(?:geometry|structure).*(?:not\s+converged|did\s+not\s+converge)\b", re.I)),
]

SUSPICIOUS_PATTERNS = [
    (
        "IMAGINARY_FREQUENCIES",
        "Imaginary frequency reported",
        re.compile(r"\bimaginary\s+frequency\b", re.I),
    ),
    (
        "NEGATIVE_FREQUENCIES",
        "Negative frequency reported",
        re.compile(r"\bnegative\s+frequency\b", re.I),
    ),
]


def parse_xtb(path: Path) -> Calculation:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    calc = Calculation(path=path)

    if _looks_like_crest(text):
        calc.program = "CREST"
    elif _looks_like_xtb(text):
        calc.program = "xTB"

    calc.version = _first_match(
        text,
        [
            r"\b(?:xTB|CREST)\s+version\s+([^\s]+)",
            r"\b(?:xTB|CREST)\s+v(?:ersion)?\s+([^\s]+)",
        ],
    )

    method = _first_match(
        text,
        [
            r"\b(GFN\d(?:-xTB)?|GFN-FF|GFN\d-xTB)\b",
        ],
    )
    if method:
        calc.method = method
    elif calc.program == "CREST":
        calc.method = "CREST"

    calc.final_energy = _last_float_match(
        text,
        [
            r"TOTAL ENERGY\s+(" + FLOAT_RE + r")\s*Eh",
            r"FINAL ENERGY\s*[:=]\s*(" + FLOAT_RE + r")\s*Eh?",
            r"\bE\s*=\s*(" + FLOAT_RE + r")\s*Eh",
            r"\benergy\s*[:=]\s*(" + FLOAT_RE + r")\s*Eh",
        ],
    )

    frequencies = _parse_frequencies(lines)
    if frequencies:
        calc.lowest_frequency = min(frequencies)
        calc.imaginary_frequency_count = sum(1 for frequency in frequencies if frequency < 0.0)

    calc.runtime_seconds = _parse_runtime_seconds(text)
    calc.termination = _parse_termination(text)
    calc.warnings.extend(_collect_warnings(lines, frequencies))
    calc.status = _classify(calc, text)
    return calc


def looks_like_xtb(path: Path) -> bool:
    try:
        head = path.read_text(errors="replace")[:8000]
    except OSError:
        return False
    lowered = head.lower()
    return _looks_like_xtb(head) or _looks_like_crest(head) or "xtb" in lowered or "crest" in lowered


def _looks_like_xtb(text: str) -> bool:
    lowered = text.lower()
    return (
        "xtb version" in lowered
        or "x t b" in lowered
        or "gfn2-xtb" in lowered
        or "gfn1-xtb" in lowered
        or re.search(r"\bxtb:\s*\d", lowered) is not None
    )


def _looks_like_crest(text: str) -> bool:
    lowered = text.lower()
    return "crest version" in lowered or re.search(r"\bcrest\b", lowered) is not None


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return None


def _last_float_match(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        matches = re.findall(pattern, text, re.I)
        if matches:
            return float(matches[-1])
    return None


def _parse_frequencies(lines: list[str]) -> list[float]:
    frequencies: list[float] = []
    for line in lines:
        match = re.search(r"\b(?:imaginary\s+)?frequency(?:\s*\d*)?\s*[:=]?\s*(" + FLOAT_RE + r")\s*cm", line, re.I)
        if match:
            frequencies.append(float(match.group(1)))
            continue
        match = re.search(r"(" + FLOAT_RE + r")\s*cm(?:\*\*|-)\s*1\b", line, re.I)
        if match:
            frequencies.append(float(match.group(1)))
    return frequencies


def _parse_runtime_seconds(text: str) -> int | None:
    patterns = [
        r"(?:wall|elapsed)[\s-]?time\s*[:=]\s*(\d+)\s*d(?:ays?)?,?\s*(\d+)\s*h(?:ours?)?,?\s*(\d+)\s*m(?:in(?:utes?)?)?,?\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:onds?)?)?",
        r"(?:wall|elapsed)[\s-]?time\s*[:=]\s*(\d+)\s*h(?:ours?)?,?\s*(\d+)\s*m(?:in(?:utes?)?)?,?\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:onds?)?)?",
        r"(?:wall|elapsed)[\s-]?time\s*[:=]\s*(\d+)\s*m(?:in(?:utes?)?)?,?\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:onds?)?)?",
        r"(?:wall|elapsed)[\s-]?time\s*[:=]\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:onds?)?)?",
        r"total\s+runtime\s*[:=]\s*(\d+)\s*s(?:ec(?:onds?)?)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        parts = match.groups(default="0")
        if len(parts) == 4:
            days, hours, minutes, seconds = (int(float(part)) for part in parts)
            return (((days * 24) + hours) * 60 + minutes) * 60 + seconds
        if len(parts) == 3:
            hours, minutes, seconds = (int(float(part)) for part in parts)
            return ((hours * 60) + minutes) * 60 + seconds
        if len(parts) == 2:
            minutes, seconds = (int(float(part)) for part in parts)
            return minutes * 60 + seconds
        if len(parts) == 1:
            return int(float(parts[0]))
    return None


def _parse_termination(text: str) -> str | None:
    lowered = text.lower()
    if (
        "normal termination" in lowered
        or "terminated normally" in lowered
        or "finished normally" in lowered
        or re.search(r"\bfinished\s+run\b", lowered) is not None
    ):
        return "normal"
    if "abnormal termination" in lowered or "fatal error" in lowered:
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
    fatal_codes = {"ABNORMAL_TERMINATION", "FATAL_ERROR", "SCF_NOT_CONVERGED", "GEOM_NOT_CONVERGED"}
    if any(warning.code in fatal_codes for warning in calc.warnings):
        return Status.FAILED
    if calc.termination == "normal":
        return Status.SUSPICIOUS if calc.warnings else Status.DONE
    if _looks_recent(calc.path) and not _has_finish_marker(text):
        return Status.RUNNING
    if calc.warnings:
        return Status.SUSPICIOUS
    return Status.UNKNOWN


def _has_finish_marker(text: str) -> bool:
    lowered = text.lower()
    return "finished" in lowered or "termination" in lowered


def _looks_recent(path: Path) -> bool:
    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age_seconds < 2 * 60 * 60
