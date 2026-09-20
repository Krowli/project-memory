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


# --- what the keyboard menu looks like -------------------------------------------
#
# The first version got the mechanics right and the screen wrong: title, note, hint
# and rows in one undifferentiated block, the answered menu left standing under the
# next one, columns that moved between questions. The person who asked for arrows
# asked again, about that. Rendering is a pure function so that it can be looked at
# here, without a terminal, one line at a time.

def strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text)


def test_the_question_marks_its_title_and_dims_the_note():
    block = menu.render_question("Pick one", "A note.", color=True)
    assert "\x1b[1mPick one\x1b[0m" in block, "the title is not bold"
    assert "\x1b[2mA note.\x1b[0m" in block, "the note is not dim"
    assert block.endswith("\r\n\r\n"), "no blank line between the question and the rows"


def test_without_colour_the_question_is_the_same_words_and_no_escape_codes():
    block = menu.render_question("Pick one", "A note.", color=False)
    assert "\x1b" not in block
    assert strip_ansi(menu.render_question("Pick one", "A note.", color=True)) == block


def test_every_detail_starts_in_the_same_column_in_both_modes():
    """The single-choice and the tick-box lists used two different label widths, so
    the columns jumped between one question and the next."""
    single = strip_ansi(menu.render_list(OPTIONS, 0, set(), False, color=False))
    multi = strip_ansi(menu.render_list(OPTIONS, 0, {1}, True, color=False))
    rows = [line for line in (single + multi).splitlines() if "first" in line
            or "second" in line or "third" in line]
    assert len(rows) == 6
    columns = {max(line.rfind(word) for word in ("first", "second", "third")) for line in rows}
    assert len(columns) == 1, f"details start in {len(columns)} different columns"


def test_only_the_cursor_row_carries_the_arrow_and_the_colour():
    rows = menu.render_list(OPTIONS, 1, set(), False, color=True).splitlines()
    assert rows[0].count("\u276f") == 0 and rows[1].count("\u276f") == 1
    assert "\x1b[36m" in rows[1], "the cursor row is not highlighted"
    assert "\x1b[36m" not in rows[0]


def test_the_key_hint_sits_under_the_rows_and_names_the_keys():
    single = strip_ansi(menu.render_list(OPTIONS, 0, set(), False, color=False))
    multi = strip_ansi(menu.render_list(OPTIONS, 0, set(), True, color=False))
    assert single.rstrip().splitlines()[-1].strip().startswith("\u2191\u2193")
    assert "enter" in single and "esc" in single
    assert "space" in multi and "space" not in single


def test_the_answer_line_names_the_question_and_the_choice():
    assert menu.render_answer("Pick one", "Gamma", color=False) == "\u2714 Pick one  Gamma\r\n"
    assert menu.render_answer("Pick one", "skipped", color=False, skipped=True) == \
        "\u2013 Pick one  skipped\r\n"


def test_no_color_turns_the_colour_off_even_on_a_terminal(monkeypatch):
    """no-color.org: the one convention every tool honours, so this one does too."""
    class Tty(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert menu.wants_color(Tty()) is True
    monkeypatch.setenv("NO_COLOR", "1")
    assert menu.wants_color(Tty()) is False
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "dumb")
    assert menu.wants_color(Tty()) is False
    assert menu.wants_color(io.StringIO()) is False, "a pipe got colour codes"


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
    # The menu is replaced by one line naming the answer. A raw byte stream cannot
    # show what the screen holds, so this checks the mechanism — cursor up, erase
    # to the end of the screen — and the line that follows it.
    assert "\x1b[J" in text, "the answered menu was left standing"
    assert "\u2714 Pick one  Gamma" in strip_ansi(text), text[-400:]
