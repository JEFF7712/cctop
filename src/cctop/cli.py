from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .export import export_calculations
from .render import plain_report
from .scan import load_many_calculations
from .tui import run_tui


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "export":
        return _export_main(argv[1:])
    return _view_main(argv)


def _view_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cctop", description="Inspect computational chemistry output files.")
    parser.add_argument("paths", nargs="*", help="Output file or directory to inspect.")
    parser.add_argument("--exclude", metavar="PATTERN", action="append", default=[], help="Glob pattern to exclude files (can be repeated).")
    args = parser.parse_args(argv)

    paths = _input_paths(args.paths)
    calculations = load_many_calculations(paths, exclude=args.exclude)
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
    parser.add_argument("--exclude", metavar="PATTERN", action="append", default=[], help="Glob pattern to exclude files (can be repeated).")
    args = parser.parse_args(argv)

    paths = _input_paths(args.paths)
    calculations = load_many_calculations(paths, exclude=args.exclude)
    if not calculations:
        print("cctop export: no supported output files found", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else Path(f"cctop_summary.{args.format}")
    root = _display_root(paths)
    export_calculations(calculations, output_path, args.format, root=root)
    print(f"wrote {output_path}")
    return 0


def _input_paths(paths: list[str]) -> list[Path]:
    if not paths:
        return [Path(".")]
    return [Path(path) for path in paths]


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
