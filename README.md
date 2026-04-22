# cctop

`cctop` is a minimal terminal dashboard for computational chemistry output folders.

- ORCA output parsing.
- Directory scan.
- Single-file inspect.
- CSV/JSON export.
- Basic terminal UI when run in a real terminal.
- No recommendations or automatic fix suggestions.

## Usage

```bash
cctop .
cctop path/to/orca.out
cctop export .
cctop export . --format json
```

When stdout is not attached to a terminal, `cctop` prints a plain text summary instead of opening the TUI.

## Install

From PyPI:

```bash
pipx install compchem-cctop
```

or:

```bash
python -m pip install compchem-cctop
```

For a local checkout:

```bash
python -m pip install -e .
```

For an isolated command-line install:

```bash
pipx install .
```

## Development

```bash
python -m pip install -e ".[dev]"
python -m cctop .
python -m unittest
```

Build release artifacts:

```bash
python -m build
```
