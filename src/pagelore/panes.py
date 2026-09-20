"""`lore dev --panes` — a two-pane browse screen, opt in on purpose.

The console's default is the line editor, and that decision stands: a redrawn
widget holds raw mode for the whole session and needs a pty test that races,
where the line editor is pipe-drivable. The panes are an *extra* screen behind
`--panes` and the internal `panes` command: browse the store by exact list or by
the same ranked search the CLI runs (in-process, so a hit here is a hit on the
command line), open a page on the right, quit back to the line editor.

Everything a keypress needs to decide is a pure function on `State` — which rows
are listed, which is selected, where the viewport starts, what is open — so the
bulk of the screen is tested the way the line editor is: called directly, no
terminal. Only the draw loop touches curses, and one pty test proves the raw
screen draws and answers keys. `curses` is POSIX and the screen needs a real
terminal, so where either is missing `--panes` says so and falls back to the
line editor instead of failing.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import curses
except ImportError:  # pragma: no cover — Windows ships no curses
    curses = None  # type: ignore[assignment]

from . import __version__
from .lib import Page, load_pages
from .search import search

DEFAULT_K = 15


@dataclass
class State:
    """What the screen remembers between keys. All fields are plain data."""

    rows: list[Page] = field(default_factory=list)
    query: str = ""            # what has been typed while the field is open
    active_query: str = ""     # what produced `rows`; "" means the full list
    selected: int = 0
    offset: int = 0
    opened: Page | None = None
    editing: bool = False      # the search field is open and accepting keys

    def visible(self, height: int) -> list[Page]:
        return self.rows[self.offset:self.offset + height]


def initial_rows(store: Path) -> list[Page]:
    """The full list, newest first — exactly what `lore list` shows."""
    pages = load_pages(store)
    pages.sort(key=lambda p: (p.updated, p.slug), reverse=True)
    return pages


def query_rows(store: Path, query: str) -> list[Page]:
    """The same ranked search the CLI runs; an empty query is the full list."""
    if not query:
        return initial_rows(store)
    return [page for _, page in search(query, store, k=DEFAULT_K)]


def move(state: State, delta: int) -> None:
    """Move the selection, clamped to the list — never out of it."""
    total = len(state.rows)
    if not total:
        return
    state.selected = max(0, min(total - 1, state.selected + delta))


def scroll(state: State, height: int) -> None:
    """Keep the selection inside the visible window."""
    if height <= 0:
        return
    if state.selected < state.offset:
        state.offset = state.selected
    elif state.selected >= state.offset + height:
        state.offset = state.selected - height + 1


def open_at(state: State) -> Page | None:
    """Open the selected row in the right pane."""
    if 0 <= state.selected < len(state.rows):
        state.opened = state.rows[state.selected]
    return state.opened


def wrap(text: str, width: int) -> list[str]:
    """Word-wrap a page body to a pane width. Display-only, and pure."""
    if width <= 1:
        return [text]
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            if current and len(current) + 1 + len(word) > width:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        lines.append(current)
    return lines


def run_guarded(store: Path, *, prog: str = "lore dev --panes") -> bool:
    """Try the screen; report and return False where the terminal cannot host it.

    The gate is the same one the console uses: both ends a real terminal. A pipe
    keeps the line editor — an agent that drives `lore dev` must not lose it.
    """
    try:
        real = sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError, OSError):
        real = False
    if not real:
        print("two-pane screen needs a real terminal; back to the line editor")
        return False
    if curses is None:
        print("two-pane screen needs curses (POSIX); back to the line editor")
        return False
    try:
        curses.wrapper(_main, store, prog=prog)
    except curses.error as exc:
        print(f"two-pane screen could not start ({exc}); back to the line editor")
        return False
    return True


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:1]
    return text[: (width - 1)] + "…"


def _draw(stdscr, store: Path, state: State, prog: str) -> None:
    """Redraw the whole screen from the state. One source of truth, no diffing."""
    stdscr.erase()
    rows, cols = stdscr.getmaxyx()
    if rows < 5 or cols < 30:
        return
    left_width = max(20, min(cols // 3, 44))
    right_x = left_width + 1
    right_width = cols - right_x - 1

    label = str(store)
    note = f' — search "{state.active_query}"' if state.active_query else ""
    prog_part = f"{prog} — pagelore {__version__} — "
    pages_part = f" — {len(state.rows)} page(s)"
    label_room = cols - 1 - len(prog_part) - len(pages_part) - len(note)
    label = "" if label_room < 8 else _truncate(label, label_room)
    stdscr.addstr(0, 0, _truncate(
        f"{prog_part}{label}{pages_part}{note}", cols - 1))
    stdscr.addstr(1, 0, "─" * max(1, cols - 1))

    body_top, body_bottom = 2, rows - 3
    view = state.visible(max(1, body_bottom - body_top))
    for i, page in enumerate(view):
        y = body_top + i
        if y > body_bottom:
            break
        text = (f"⚠ superseded by {page.superseded_by} — " if page.superseded_by else "")
        text += f"{page.slug} — {page.title}"
        attr = curses.A_REVERSE if i == state.selected - state.offset else curses.A_NORMAL
        stdscr.addstr(y, 1, _truncate(text, left_width - 2).ljust(left_width - 2), attr)

    if right_width > 4 and state.opened is not None:
        opened = state.opened
        stdscr.addstr(body_top, right_x, _truncate(f"# {opened.title}", right_width),
                      curses.A_BOLD)
        for i, line in enumerate(wrap(opened.body, right_width), start=1):
            y = body_top + i
            if y > body_bottom:
                break
            stdscr.addstr(y, right_x, _truncate(line, right_width))

    prompt = f"search: {state.query}" if state.editing else \
        "↑↓/jk move · ↵ open · / search · c clear query · q quit"
    try:
        curses.curs_set(1 if state.editing else 0)
    except curses.error:
        pass
    stdscr.addstr(rows - 1, 0, _truncate(prompt, cols - 1).ljust(cols - 1))
    stdscr.refresh()


def _main(stdscr, store: Path, *, prog: str) -> None:  # pragma: no cover — needs a terminal
    """The screen itself: read a key, decide, redraw. `q` is back to the editor."""
    state = State(rows=initial_rows(store))
    while True:
        _draw(stdscr, store, state, prog)
        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            continue
        if state.editing:
            if key in (ord("\n"), 10, 13):
                state.active_query = state.query
                state.editing = False
                state.rows = query_rows(store, state.active_query)
                state.selected = 0
                state.offset = 0
            elif key == 27:  # Esc cancels the edit; the applied query stays
                state.query = state.active_query
                state.editing = False
            elif key in (8, 127, curses.KEY_BACKSPACE):
                state.query = state.query[:-1]
            elif 32 <= key <= 126:
                state.query += chr(key)
            continue
        if key in (ord("q"), ord("Q")):
            return
        if key in (curses.KEY_UP, ord("k")):
            move(state, -1)
        elif key in (curses.KEY_DOWN, ord("j")):
            move(state, 1)
        elif key in (ord("\n"), 10, 13):
            open_at(state)
        elif key == ord("/"):
            state.query = state.active_query
            state.editing = True
        elif key == ord("c"):
            state.active_query = ""
            state.query = ""
            state.rows = initial_rows(store)
            state.selected = 0
            state.offset = 0
            state.opened = None
        scroll(state, max(1, stdscr.getmaxyx()[0] - 4))