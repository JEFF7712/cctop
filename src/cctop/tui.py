from __future__ import annotations

import curses
from pathlib import Path

from .models import Calculation
from .render import format_float, format_seconds, single_report, status_line


def run_tui(calculations: list[Calculation], root: Path | None = None) -> None:
    curses.wrapper(_main, calculations, root)


def _main(stdscr: curses.window, calculations: list[Calculation], root: Path | None) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    selected = 0
    offset = 0

    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()
        _draw(stdscr, calculations, root, selected, offset, height, width)
        key = stdscr.getch()

        if key in (ord("q"), 27):
            break
        if key in (curses.KEY_DOWN, ord("j")) and selected < len(calculations) - 1:
            selected += 1
        elif key in (curses.KEY_UP, ord("k")) and selected > 0:
            selected -= 1
        elif key == curses.KEY_NPAGE:
            selected = min(len(calculations) - 1, selected + max(1, height - 6))
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - max(1, height - 6))

        table_height = max(1, height - 8)
        if selected < offset:
            offset = selected
        elif selected >= offset + table_height:
            offset = selected - table_height + 1


def _draw(
    stdscr: curses.window,
    calculations: list[Calculation],
    root: Path | None,
    selected: int,
    offset: int,
    height: int,
    width: int,
) -> None:
    if height < 10 or width < 70:
        _addstr(stdscr, 0, 0, "cctop needs a larger terminal. Press q to quit.", width)
        return

    _addstr(stdscr, 0, 0, f"cctop | {status_line(calculations)}", width, curses.A_BOLD)
    _addstr(stdscr, 1, 0, "Use j/k or arrow keys to move. q quits.", width)

    split = max(44, width // 2)
    _draw_table(stdscr, calculations, root, selected, offset, 3, split - 1, height - 4)
    _draw_details(stdscr, calculations[selected] if calculations else None, root, 3, split + 1, width - split - 2, height - 4)
    stdscr.refresh()


def _draw_table(
    stdscr: curses.window,
    calculations: list[Calculation],
    root: Path | None,
    selected: int,
    offset: int,
    y: int,
    width: int,
    height: int,
) -> None:
    _addstr(stdscr, y, 0, "Calculations", width, curses.A_BOLD)
    _addstr(stdscr, y + 1, 0, f"{'Status':<11} {'File':<24} {'Energy':>12} {'Im':>3}", width)
    visible = calculations[offset : offset + max(0, height - 2)]

    for index, calc in enumerate(visible, start=offset):
        line_y = y + 2 + index - offset
        path = _display_path(calc, root)
        line = (
            f"{calc.status.value:<11} "
            f"{path:<24.24} "
            f"{format_float(calc.final_energy):>12} "
            f"{_none_dash(calc.imaginary_frequency_count):>3}"
        )
        attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
        _addstr(stdscr, line_y, 0, line, width, attr)


def _draw_details(
    stdscr: curses.window,
    calc: Calculation | None,
    root: Path | None,
    y: int,
    x: int,
    width: int,
    height: int,
) -> None:
    _addstr(stdscr, y, x, "Details", width, curses.A_BOLD)
    if calc is None:
        _addstr(stdscr, y + 1, x, "No calculations found.", width)
        return

    report_lines = single_report(calc, root=root).splitlines()
    report_lines.append("")
    report_lines.append(f"Runtime: {format_seconds(calc.runtime_seconds)}")

    for index, line in enumerate(report_lines[: max(0, height - 1)], start=1):
        _addstr(stdscr, y + index, x, line, width)


def _display_path(calc: Calculation, root: Path | None) -> str:
    if root is None:
        return str(calc.path.name)
    try:
        return str(calc.path.relative_to(root))
    except ValueError:
        return str(calc.path.name)


def _none_dash(value: object | None) -> str:
    return "--" if value is None else str(value)


def _addstr(stdscr: curses.window, y: int, x: int, text: str, width: int, attr: int = curses.A_NORMAL) -> None:
    if width <= 0:
        return
    try:
        stdscr.addstr(y, x, text[: max(0, width - 1)], attr)
    except curses.error:
        pass
