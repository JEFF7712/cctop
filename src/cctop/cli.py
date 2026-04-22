from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .export import export_calculations
from .render import plain_report
from .scan import load_calculations
from .tui import run_tui


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "export":
        return _export_main(argv[1:])
    return _view_main(argv)


def _view_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="cctop", description="Inspect computational chemistry output files.")
    parser.add_argument("path", nargs="?", default=".", help="Output file or directory to inspect.")
    args = parser.parse_args(argv)

    path = Path(args.path)
    calculations = load_calculations(path)
    root = path.expanduser().resolve() if path.is_dir() else path.expanduser().resolve().parent

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
    parser.add_argument("path", nargs="?", default=".", help="Output file or directory to scan.")
    parser.add_argument("--format", choices=("csv", "json"), default="csv", help="Export format.")
    parser.add_argument("--output", "-o", help="Output path.")
    args = parser.parse_args(argv)

    path = Path(args.path)
    calculations = load_calculations(path)
    if not calculations:
        print("cctop export: no supported output files found", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else Path(f"cctop_summary.{args.format}")
    root = path.expanduser().resolve() if path.is_dir() else path.expanduser().resolve().parent
    export_calculations(calculations, output_path, args.format, root=root)
    print(f"wrote {output_path}")
    return 0
