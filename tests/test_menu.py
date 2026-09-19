"""The keyboard menu, and the numbered prompt it falls back to.

The reason this file exists at all: the first person to run `lore init` typed a
digit, got a wall of text, and asked why it was not a normal menu with arrow keys
like every other tool they use. It was a fair question, and the honest answer was
that I had measured whether the wizard did the right thing and never once looked at
what it was like to use.

Terminal behaviour cannot be asserted from a test with no terminal, so the key
handling is a pure function over bytes and that is what is tested here. One pty test
at the end drives real arrows through a real terminal, which is the only way to prove
the wiring those pure tests bypass.
"""
import io

import conftest
import pytest

from pagelore import menu

OPTIONS = [("a", "Alpha", "first"), ("b", "Beta", "second"), ("c", "Gamma", "third")]


@pytest.mark.parametrize("data, expected", [
    ("\x1b[A", "up"), ("\x1b[B", "down"),
    ("\x1bOA", "up"), ("\x1bOB", "down"),      # application cursor mode
    ("\xe0H", "up"), ("\xe0P", "down"),        # Windows
    ("\x00H", "up"), ("\x00P", "down"),
    ("k", "up"), ("j", "down"),
    ("\r", "enter"), ("\n", "enter"), (" ", "space"),
    ("\x1b", "quit"), ("\x03", "quit"), ("q", "quit"),
    ("2", "2"),                                 # a digit is still an answer
    ("\x1b[C", ""), ("z", ""), ("", ""),        # nothing we act on
])
def test_each_sequence_decodes_to_one_key(data, expected):
    assert menu.decode(data) == expected


def test_a_bare_escape_and_an_arrow_are_told_apart():
    """They share a first byte. Reading one byte and stopping would make every arrow
    a cancel, which is the difference between a menu and a trap."""
    assert menu.decode("\x1b") == "quit"
    assert menu.decode("\x1b[A") == "up"


def test_a_stream_with_no_terminal_behind_it_is_not_a_keyboard():
    """`isatty` alone is not enough: a stream can claim to be a terminal and have no
    descriptor to put into raw mode. Getting this wrong means the wizard blocks on a
    keypress in CI that is never coming."""
    assert menu.has_keyboard(io.StringIO("")) is False

    class Liar(io.StringIO):
        def isatty(self):
            return True

    assert menu.has_keyboard(Liar("")) is False


def test_without_a_keyboard_the_question_is_numbered_and_answerable():
    out = io.StringIO()
    picked = menu.ask("Pick one", "", OPTIONS, stdin=io.StringIO("2\n"), out=out,
                      keyboard=False)
    assert picked == ["b"]
    text = out.getvalue()
    assert "1) Alpha" in text and "3) Gamma" in text
    assert "Choice" in text


def test_the_numbered_path_takes_several_and_keeps_their_order_once():
    picked = menu.ask("Pick some", "", OPTIONS, multi=True,
                      stdin=io.StringIO("3 1 3\n"), out=io.StringIO(), keyboard=False)
    assert picked == ["c", "a"]


def test_an_unrecognised_answer_says_so_rather_than_guessing():
    out = io.StringIO()
    picked = menu.ask("Pick one", "", OPTIONS, stdin=io.StringIO("nine\n"), out=out,
                      keyboard=False)
    assert picked == []
    assert "nothing recognised" in out.getvalue()


def test_an_empty_answer_chooses_nothing_rather_than_the_first_thing():
    """Every caller treats an empty result as a real answer. A menu that returns the
    highlighted row when someone pressed enter to get out of it would connect an
    agent nobody asked to connect."""
    assert menu.ask("Pick one", "", OPTIONS, stdin=io.StringIO("\n"),
                    out=io.StringIO(), keyboard=False) == []


def test_confirm_defaults_to_yes_on_the_numbered_path():
    assert menu.confirm("Go?", stdin=io.StringIO("\n"), out=io.StringIO(),
                        keyboard=False) is True
    assert menu.confirm("Go?", stdin=io.StringIO("n\n"), out=io.StringIO(),
                        keyboard=False) is False


@conftest.needs_posix
def test_arrows_move_the_cursor_on_a_real_terminal(tmp_path):
    """What every test above bypasses: raw mode, the escape sequences a terminal
    actually sends, and the redraw. Driven through a pty because there is no other
    way to prove it."""
    import os
    import pty
    import sys

    script = tmp_path / "drive.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(conftest.REPO / 'src')!r})\n"
        "from pagelore import menu\n"
        "picked = menu.ask('Pick one', '', "
        "[('a','Alpha','first'),('b','Beta','second'),('c','Gamma','third')])\n"
        "sys.stdout.write('PICKED=' + ','.join(picked) + '\\n')\n",
        encoding="utf-8")

    pid, fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, str(script)])

    seen = b""
    try:
        while b"Gamma" not in seen:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            seen += chunk
        os.write(fd, b"\x1b[B\x1b[B\r")        # down, down, enter
        while b"PICKED=" not in seen:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            seen += chunk
    except OSError:
        pass
    finally:
        os.close(fd)
        os.waitpid(pid, 0)

    text = seen.decode("utf-8", "replace")
    assert "PICKED=c" in text, text[-400:]
    assert "❯" in text, "the cursor was never drawn"
