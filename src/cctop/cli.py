from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .export import export_calculations
from .orca import parse_orca_optimization_history, write_orca_optimization_history
from .render import plain_report
from .scan import load_many_calculations
from .tui import run_tui


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "export":
        return _export_main(argv[1:])
    if argv and argv[0] == "orca-history":
        return _orca_history_main(argv[1:])
    return _view_main(argv)


def _view_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cctop", description="Inspect computational chemistry output files.")
    parser.add_argument("paths", nargs="*", help="Output file or directory to inspect.")
    args = parser.parse_args(argv)

    paths = _input_paths(args.paths)
    calculations = load_many_calculations(paths)
    root = _display_root(paths)

    if not calculations:
        print("cctop: no supported output files found")
        return 1

    if sys.stdin.isatty() and sys.stdout.isatty():
        run_tui(calculations, root=root)
    else:
        print(plain_report(calculations, root=root))
    return 0


def _export_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cctop export", description="Export a cctop scan summary.")
    parser.add_argument("paths", nargs="*", help="Output file or directory to scan.")
    parser.add_argument("--format", choices=("csv", "json"), default="csv", help="Export format.")
    parser.add_argument("--output", "-o", help="Output path.")
    args = parser.parse_args(argv)

    paths = _input_paths(args.paths)
    calculations = load_many_calculations(paths)
    if not calculations:
        print("cctop export: no supported output files found", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else Path(f"cctop_summary.{args.format}")
    root = _display_root(paths)
    export_calculations(calculations, output_path, args.format, root=root)
    print(f"wrote {output_path}")
    return 0


def _orca_history_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cctop orca-history",
        description="Export ORCA optimization energy and bond-distance histories.",
    )
    parser.add_argument("path", help="ORCA output file or a directory containing orca.out.")
    parser.add_argument("atom_a", type=int, help="First atom index, zero-based.")
    parser.add_argument("atom_b", type=int, help="Second atom index, zero-based.")
    parser.add_argument(
        "--trajectory",
        "-t",
        help="Trajectory XYZ path. Defaults to <output_stem>_trj.xyz.",
    )
    parser.add_argument(
        "--energy-output",
        default="orca_energy.txt",
        help="Energy history output path.",
    )
    parser.add_argument(
        "--distance-output",
        default="orca_distance.txt",
        help="Bond-distance history output path.",
    )
    args = parser.parse_args(argv)

    output_path = _orca_output_path(Path(args.path))
    trajectory_path = Path(args.trajectory) if args.trajectory else None
    try:
        history = parse_orca_optimization_history(
            output_path,
            args.atom_a,
            args.atom_b,
            trajectory_path,
        )
    except (OSError, ValueError) as exc:
        print(f"cctop orca-history: {exc}", file=sys.stderr)
        return 1

    energy_output_path = Path(args.energy_output)
    distance_output_path = Path(args.distance_output)
    try:
        write_orca_optimization_history(history, energy_output_path, distance_output_path)
    except OSError as exc:
        print(f"cctop orca-history: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {energy_output_path}")
    print(f"wrote {distance_output_path}")
    if len(history.energies) != len(history.distances):
        print(
            "warning: energy and trajectory frame counts differ "
            f"({len(history.energies)} energies, {len(history.distances)} distances)",
            file=sys.stderr,
        )
    return 0


def _input_paths(paths: list[str]) -> list[Path]:
    if not paths:
        return [Path(".")]
    return [Path(path) for path in paths]


def _orca_output_path(path: Path) -> Path:
    path = path.expanduser()
    if path.is_dir():
        return path / "orca.out"
    return path


def _display_root(paths: list[Path]) -> Path | None:
    resolved = [path.expanduser().resolve() for path in paths]
    if len(resolved) == 1:
        path = resolved[0]
        return path if path.is_dir() else path.parent
    try:
        roots = [path if path.is_dir() else path.parent for path in resolved]
        return Path(os.path.commonpath(roots))
    except (OSError, ValueError):
        return None
