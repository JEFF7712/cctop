from __future__ import annotations

import re
import time
from dataclasses import dataclass
from math import dist
from pathlib import Path

from .models import Calculation, Status, Warning


FLOAT_RE = r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?"

FATAL_PATTERNS = [
    ("ORCA_ERROR", "ORCA finished by error termination", re.compile(r"\bORCA finished by error termination\b", re.I)),
    ("SCF_NOT_CONVERGED", "SCF did not converge", re.compile(r"\bSCF\s+NOT\s+CONVERGED\b", re.I)),
    ("ERROR", "Error marker found", re.compile(r"\b(error termination|aborting the run|fatal error)\b", re.I)),
]

SUSPICIOUS_PATTERNS = [
    (
        "GEOM_NOT_CONVERGED",
        "Geometry optimization did not converge",
        re.compile(
            r"(?:geometry\s+)?optimization\s+(?:has\s+)?(?:did\s+not|not)\s+converge(?:d)?\b",
            re.I,
        ),
    ),
    (
        "MAX_ITER",
        "Maximum iteration limit was reached",
        re.compile(
            r"(?:maximum number of.*iterations|maxiter).*(?:reached|exceeded)"
            r"|(?:reached|exceeded).*(?:maximum number of.*iterations|maxiter)",
            re.I,
        ),
    ),
]

BASIS_HINTS = (
    "def2",
    "cc-p",
    "aug-cc",
    "6-",
    "3-",
    "pc-",
    "pcseg",
    "ano",
    "sto-",
    "ma-",
)

METHOD_SKIP = {
    "opt",
    "freq",
    "engrad",
    "tightscf",
    "veryslowscf",
    "slowscf",
    "normalprint",
    "largeprint",
    "rijcosx",
    "ri",
    "d3",
    "d3bj",
    "d4",
    "grid4",
    "grid5",
    "grid6",
    "finalgrid5",
    "finalgrid6",
    "nososcf",
    "miniprint",
    "sp",
}


@dataclass(frozen=True, slots=True)
class OrcaOptimizationHistory:
    energies: list[float]
    distances: list[float]
    trajectory_path: Path


def parse_orca(path: Path) -> Calculation:
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    calc = Calculation(path=path, program="ORCA")

    calc.version = _first_match(text, r"Program Version\s+([^\s]+)")
    command_line = _find_orca_command(lines)
    if command_line:
        calc.method, calc.basis = _parse_method_basis(command_line)

    charge_mult = _find_charge_multiplicity(lines)
    if charge_mult:
        calc.charge, calc.multiplicity = charge_mult

    energies = [float(match) for match in re.findall(r"FINAL SINGLE POINT ENERGY\s+(" + FLOAT_RE + r")", text)]
    if energies:
        calc.final_energy = energies[-1]

    calc.gibbs_energy = _last_float_match(
        text,
        [
            r"Final Gibbs free energy\s+\.+\s+(" + FLOAT_RE + r")",
            r"Total Gibbs free energy\s+\.+\s+(" + FLOAT_RE + r")",
            r"G-E\(el\)\s+\.+\s+(" + FLOAT_RE + r")",
        ],
    )

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


def parse_orca_optimization_history(
    output_path: Path,
    atom_a: int,
    atom_b: int,
    trajectory_path: Path | None = None,
) -> OrcaOptimizationHistory:
    if atom_a < 0 or atom_b < 0:
        raise ValueError("atom indices must be zero-based non-negative integers")
    if atom_a == atom_b:
        raise ValueError("atom indices must refer to two different atoms")

    text = output_path.read_text(errors="replace")
    energy_pattern = r"FINAL SINGLE POINT ENERGY\s+(" + FLOAT_RE + r")"
    energies = [float(match) for match in re.findall(energy_pattern, text)]

    trajectory_path = trajectory_path or output_path.with_name(f"{output_path.stem}_trj.xyz")
    distances = _parse_orca_trajectory_distances(trajectory_path, atom_a, atom_b)
    return OrcaOptimizationHistory(
        energies=energies,
        distances=distances,
        trajectory_path=trajectory_path,
    )


def write_orca_optimization_history(
    history: OrcaOptimizationHistory,
    energy_output_path: Path,
    distance_output_path: Path,
) -> None:
    _write_series(energy_output_path, "step energy_hartree", history.energies)
    _write_series(distance_output_path, "step distance_angstrom", history.distances)


def looks_like_orca(path: Path) -> bool:
    try:
        head = path.read_text(errors="replace")[:8000]
    except OSError:
        return False
    return "O   R   C   A" in head or "ORCA" in head and "Program Version" in head


def _parse_orca_trajectory_distances(path: Path, atom_a: int, atom_b: int) -> list[float]:
    lines = path.read_text(errors="replace").splitlines()
    distances: list[float] = []
    index = 0
    frame_number = 0

    while index < len(lines):
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            break

        try:
            atom_count = int(lines[index].strip())
        except ValueError as exc:
            raise ValueError(f"{path}: expected atom count at line {index + 1}") from exc

        frame_number += 1
        coordinate_start = index + 2
        coordinate_end = coordinate_start + atom_count
        if coordinate_end > len(lines):
            raise ValueError(f"{path}: frame {frame_number} is truncated")
        if atom_a >= atom_count or atom_b >= atom_count:
            raise ValueError(
                f"{path}: atom index out of range for frame {frame_number} with {atom_count} atoms"
            )

        coord_a = _parse_xyz_coordinate(
            lines[coordinate_start + atom_a],
            path,
            coordinate_start + atom_a + 1,
        )
        coord_b = _parse_xyz_coordinate(
            lines[coordinate_start + atom_b],
            path,
            coordinate_start + atom_b + 1,
        )
        distances.append(dist(coord_a, coord_b))
        index = coordinate_end

    return distances


def _parse_xyz_coordinate(line: str, path: Path, line_number: int) -> tuple[float, float, float]:
    parts = line.split()
    if len(parts) < 4:
        raise ValueError(f"{path}: expected XYZ coordinate at line {line_number}")
    try:
        return float(parts[1]), float(parts[2]), float(parts[3])
    except ValueError as exc:
        raise ValueError(f"{path}: invalid XYZ coordinate at line {line_number}") from exc


def _write_series(path: Path, header: str, values: list[float]) -> None:
    lines = [f"# {header}"]
    lines.extend(f"{index} {value:.12f}" for index, value in enumerate(values))
    path.write_text("\n".join(lines) + "\n")


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.I)
    return match.group(1) if match else None


def _last_float_match(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        matches = re.findall(pattern, text, re.I)
        if matches:
            return float(matches[-1])
    return None


def _find_orca_command(lines: list[str]) -> str | None:
    in_input = False
    for line in lines:
        if "INPUT FILE" in line:
            in_input = True
            continue
        if in_input:
            stripped = _strip_input_prefix(line)
            if stripped.startswith("!"):
                return stripped

    for line in lines[:500]:
        stripped = _strip_input_prefix(line)
        if stripped.startswith("!"):
            return stripped
    return None


def _strip_input_prefix(line: str) -> str:
    stripped = line.strip()
    match = re.match(r"^\|\s*\d+>\s*(.*)", stripped)
    return match.group(1).strip() if match else stripped


def _parse_method_basis(command_line: str) -> tuple[str | None, str | None]:
    cleaned = command_line.lstrip("!").strip()
    tokens = [token.strip() for token in cleaned.split() if token.strip()]
    method = None
    basis = None

    for token in tokens:
        lowered = token.lower()
        if basis is None and lowered.startswith(BASIS_HINTS):
            basis = token
            continue
        if method is None and lowered not in METHOD_SKIP and not lowered.startswith(("%", "smd(")):
            method = token

    return method, basis


def _find_charge_multiplicity(lines: list[str]) -> tuple[int, int] | None:
    pattern = re.compile(r"^\*\s+(?:xyz|int|gzmt|xyzfile)\s+(-?\d+)\s+(\d+)", re.I)
    for line in lines:
        match = pattern.match(_strip_input_prefix(line))
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


def _parse_frequencies(lines: list[str]) -> list[float]:
    latest_frequencies: list[float] = []
    current_frequencies: list[float] = []
    in_block = False
    for line in lines:
        if "VIBRATIONAL FREQUENCIES" in line:
            current_frequencies = []
            in_block = True
            continue
        if in_block and line.strip().startswith("NORMAL MODES"):
            latest_frequencies = current_frequencies
            current_frequencies = []
            in_block = False
            continue
        if not in_block:
            continue

        match = re.search(r"^\s*\d+\s*:\s*(" + FLOAT_RE + r")\s+cm\*\*-1", line)
        if match:
            current_frequencies.append(float(match.group(1)))

    if in_block:
        latest_frequencies = current_frequencies
    return latest_frequencies


def _parse_runtime_seconds(text: str) -> int | None:
    match = re.search(
        r"TOTAL RUN TIME:\s*(\d+)\s+days\s+(\d+)\s+hours\s+(\d+)\s+minutes\s+(\d+)\s+seconds",
        text,
        re.I,
    )
    if not match:
        return None
    days, hours, minutes, seconds = (int(part) for part in match.groups())
    return (((days * 24) + hours) * 60 + minutes) * 60 + seconds


def _parse_termination(text: str) -> str | None:
    if re.search(r"\*\*\*\*ORCA TERMINATED NORMALLY\*\*\*\*", text):
        return "normal"
    if re.search(r"\bORCA finished by error termination\b", text, re.I):
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
    fatal_codes = {"ORCA_ERROR", "ERROR"}
    if any(warning.code in fatal_codes for warning in calc.warnings):
        return Status.FAILED
    if calc.termination == "normal":
        if calc.warnings:
            return Status.SUSPICIOUS
        return Status.DONE
    if any(warning.code == "SCF_NOT_CONVERGED" for warning in calc.warnings):
        return Status.FAILED
    if _looks_recent(calc.path) and "ORCA TERMINATED NORMALLY" not in text:
        return Status.RUNNING
    return Status.UNKNOWN


def _looks_recent(path: Path) -> bool:
    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age_seconds < 2 * 60 * 60
