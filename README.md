# cctop

`cctop` is a minimal terminal dashboard for computational chemistry output folders.

![cctop demo terminal output](assets/cctop.png)

- ORCA output parsing.
- Directory scan.
- Single-file inspect.
- CSV/JSON export.
- Basic terminal UI when run in a real terminal.

## Support

Current:

- ORCA: status, final energy, method/basis, charge/multiplicity, Gibbs energy, frequencies, runtime, and common warning markers.

Planned:

- VASP: `OUTCAR`, `OSZICAR`, and `vasprun.xml` job status, energies, and convergence signals.
- Gaussian: `.log`/`.out` status, route info, energies, frequencies, and termination markers.
- Q-Chem: output status, energies, methods, frequencies, and convergence markers.
- xTB/CREST: quick status and energy summaries for screening workflows.

## Usage

```bash
cctop .
cctop path/to/orca.out
cctop export .
cctop export . --format json
```

When stdout is not attached to a terminal, `cctop` prints a plain text summary instead of opening the TUI.

Try the demo data:

```bash
cctop testing/demo_orca_project
```

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
