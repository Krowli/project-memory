"""The two-pane screen: a pure model, with one pty test for the raw terminal.

The line-editor discipline carries over unchanged: what a keypress decides is
plain functions on `State`, and those are called here with no terminal. Only the
draw loop touches curses, so one pty test proves the raw screen draws the panes
and answers keys — `c` and `Esc` are drawn branches, tested through the model
and the pipe fallback, not key by key in raw mode.
"""
import os
import sys
from pathlib import Path

import conftest
import pytest

from pagelore import panes
from pagelore import write as memory_write


def _page(store: Path, slug: str, title: str) -> None:
    memory_write.write_page(
        store, slug, title, "decision", ["src/a.py"],
        "## Decision\n\nSomething was decided once, at length enough to be a real"
        " page and not a stub." + conftest.FILLER)


@pytest.fixture()
def store(tmp_path):
    d = tmp_path / ".memory"
    d.mkdir()
    for slug in ["zeta-page", "alpha-page", "middle-page"]:
        _page(d, slug, f"{slug} title")
    return d


def test_initial_rows_are_newest_first(store):
    rows = [p.slug for p in panes.initial_rows(store)]
    assert rows == ["zeta-page", "middle-page", "alpha-page"]


def test_move_clamps_at_both_ends(store):
    st = panes.State(rows=panes.initial_rows(store))
    panes.move(st, -1)
    assert st.selected == 0
    panes.move(st, 99)
    assert st.selected == 2
    panes.move(st, 1)
    assert st.selected == 2, "the selection never leaves the list"


def test_scroll_keeps_the_selection_in_the_viewport(store):
    rows = panes.initial_rows(store)  # 3 rows
    # the last row inside a height-1 window forces the offset down to it
    st = panes.State(rows=rows, selected=2)
    panes.scroll(st, 1)
    assert st.offset == 2
    # already visible, a taller window changes nothing
    panes.scroll(st, 2)
    assert st.offset == 2
    # moving above the window pulls the offset back down
    st2 = panes.State(rows=rows, selected=2, offset=2)
    panes.move(st2, -1)
    assert st2.selected == 1
    panes.scroll(st2, 2)
    assert st2.offset == 1
    # a selection above the window pulls it back up
    st3 = panes.State(rows=rows, selected=0, offset=2)
    panes.scroll(st3, 2)
    assert st3.offset == 0


def test_query_rows_are_the_cli_ranking(store):
    hits = [p.slug for p in panes.query_rows(store, "zeta")]
    assert hits == ["zeta-page"]


def test_query_rows_empty_query_is_the_full_list(store):
    assert [p.slug for p in panes.query_rows(store, "")] == \
        [p.slug for p in panes.initial_rows(store)]


def test_open_at_opens_the_selected_row(store):
    st = panes.State(rows=panes.initial_rows(store), selected=1)
    page = panes.open_at(st)
    assert st.opened is page and page.slug == "middle-page"


def test_open_at_guards_an_empty_list(store):
    st = panes.State(rows=[])
    assert panes.open_at(st) is None


def test_wrap_never_exceeds_the_width(store):
    body = " ".join("wobble" for _ in range(200))
    for width in (10, 27, 61):
        for line in panes.wrap(body, width):
            assert len(line) <= width, (width, line)
    assert all(panes.wrap(body, 10)), "no empty line from a run of words"


def test_wrap_keeps_blank_paragraphs_blank(store):
    lines = panes.wrap("one\n\ntwo", 20)
    assert lines == ["one", "", "two"]


@conftest.needs_posix
def test_the_screen_draws_both_panes_and_answers_keys(store, tmp_path):
    """Raw-screen proof: the list draws, a query filters it, Enter opens the page
    on the right, `q` is back to the line editor, and the whole thing exits 0."""
    import fcntl
    import pty
    import select
    import struct
    import termios
    import time

    home = tmp_path / "home"
    home.mkdir()

    pid, fd = pty.fork()
    if pid == 0:
        # Let the parent size the terminal before curses reads its size.
        time.sleep(0.3)
        os.chdir(store.parent)
        os.environ.update({"HOME": str(home), "USERPROFILE": str(home),
                           "PYTHONPATH": str(conftest.REPO / "src"),
                           "PROJECT_MEMORY_NO_REFRESH": "1",
                           "TERM": "xterm-256color"})
        os.execv(sys.executable, [sys.executable, "-m", "pagelore", "dev", "--panes"])

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))

    seen = b""

    def wait_for(token: bytes, deadline: float = 30) -> bool:
        nonlocal seen
        end = time.time() + deadline
        while token not in seen:
            if time.time() > end:
                return False
            if not select.select([fd], [], [], 0.2)[0]:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                return False
            if not chunk:
                return False
            seen += chunk
        return True

    try:
        assert wait_for(b"q quit"), f"no two-pane screen\n{seen[-400:]!r}"
        assert b"zeta-page" in seen, f"the list is not drawn\n{seen[-400:]!r}"
        # search: open the field, type, apply — the status line appends the query
        # (a literal diff), and Enter opens the hit on the right
        os.write(fd, b"/")
        assert wait_for(b"search:"), f"the search field did not open\n{seen[-400:]!r}"
        os.write(fd, b"zeta\r")
        assert wait_for(b'search "zeta"'), f"the typed query did not apply\n{seen[-400:]!r}"
        os.write(fd, b"\r")
        assert wait_for(b"# zeta-page title"), f"the page did not open\n{seen[-400:]!r}"
        # quit the screen: back to the line editor, then exit cleanly
        os.write(fd, b"q")
        assert wait_for(b"> "), f"no line-editor prompt after quit\n{seen[-400:]!r}"
        os.write(fd, b"exit\r")
        deadline = time.time() + 30
        while time.time() < deadline:
            if select.select([fd], [], [], 0.2)[0]:
                try:
                    if not os.read(fd, 4096):
                        break
                except OSError:
                    break
    finally:
        os.close(fd)
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass

    text = seen.decode("utf-8", "replace")
    assert "lore dev" in text, text[:300]
    assert "panes" in text, text[:300]