"""A keyboard menu, and the numbered prompt it falls back to.

Two ways to answer one question, chosen by what is on the other end:

- A real terminal gets arrows, space and enter, redrawn in place. This is what a
  person expects, and the first user to run `lore init` said so in the bluntest
  available terms.
- Anything else — a pipe, a CI job, a test driving StringIO — gets the numbered
  prompt, which is the only thing that works when there is no terminal to put
  into raw mode.

The split is deliberate and it is not a fallback in the apologetic sense. The
numbered path is the one that has to keep working: `lore init --agent claude
--yes` runs in scripts, and the wizard must never stall waiting for a keypress
that is not coming. So the question is asked in one place and answered by
whichever half the caller can actually use.

`decode` is a pure function over bytes, which is the whole reason the key
handling is testable at all. Terminal behaviour cannot be asserted from a test
that has no terminal; a byte sequence can.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager

# One escape sequence per key, both the normal and the application-cursor forms
# that some terminals send after `smkx`. j/k because anyone who would notice their
# absence will try them.
SEQUENCES = {
    "\x1b[A": "up", "\x1bOA": "up", "k": "up",
    "\x1b[B": "down", "\x1bOB": "down", "j": "down",
    "\r": "enter", "\n": "enter",
    " ": "space",
    "\x03": "quit", "\x04": "quit", "\x1b": "quit", "q": "quit",
    # Windows sends a two-byte sequence led by \xe0 (or \x00 for some keys).
    "\xe0H": "up", "\x00H": "up",
    "\xe0P": "down", "\x00P": "down",
}


def decode(data: str) -> str:
    """What key those bytes were. '' when it is nothing we act on.

    Digits come back as themselves, so a person who ignores the arrows entirely
    and presses 2 still gets what they meant.
    """
    if data in SEQUENCES:
        return SEQUENCES[data]
    if len(data) == 1 and data.isdigit():
        return data
    return ""


# One label column for every question, so the columns do not move between one
# question and the next. Wider than the widest label the wizard uses.
WIDTH = 20

_CODES = {"bold": "1", "dim": "2", "cyan": "36", "green": "32"}


def paint(text: str, style: str, color: bool) -> str:
    """`text` in one SGR style, or unchanged when colour is off or the text is empty."""
    if not color or not text:
        return text
    return f"\x1b[{_CODES[style]}m{text}\x1b[0m"


def wants_color(out) -> bool:
    """Whether to colour what goes to `out`.

    `NO_COLOR` set (no-color.org) or `TERM=dumb` says no; so does a stream that is
    not a terminal, because a pipe reading escape codes is the one thing every
    scripted caller of this wizard would have to strip.
    """
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    try:
        return bool(out.isatty())
    except (AttributeError, ValueError):
        return False


def render_question(title: str, note: str, color: bool) -> str:
    """The question block: `? title`, its note, and a blank line before the rows.

    Pure so that the screen can be looked at without a terminal. Every line ends in
    `\\r\\n` because the keyboard menu prints inside raw mode, where a bare line
    feed does not return the carriage.
    """
    lines = [f"{paint('?', 'cyan', color)} {paint(title, 'bold', color)}"]
    if note:
        lines.append(f"  {paint(note, 'dim', color)}")
    lines.append("")
    return "".join(f"{line}\r\n" for line in lines)


def render_list(options, cursor: int, picked: set, multi: bool, color: bool) -> str:
    """The rows, a blank line, and the key hint under them.

    Redrawn in place on every keypress, so each line starts with erase-line: a
    label that shrank would otherwise leave its tail on the screen.
    """
    lines = []
    for i, (_, label, detail) in enumerate(options):
        here = i == cursor
        arrow = "❯" if here else " "
        box = ("[x] " if i in picked else "[ ] ") if multi else ""
        cell = f"{label:<{WIDTH - len(box)}}"    # the box eats into the label column
        if here:
            arrow, cell = paint(arrow, "cyan", color), paint(cell, "cyan", color)
        lines.append(f"  {arrow} {box}{cell} {paint(detail, 'dim', color)}".rstrip())
    keys = "space toggle · enter confirm" if multi else "enter choose"
    lines.append("")
    lines.append(f"  {paint(f'↑↓ move · {keys} · esc skip', 'dim', color)}")
    return "".join(f"\x1b[2K{line}\r\n" for line in lines)


def render_answer(title: str, answer: str, color: bool, skipped: bool = False) -> str:
    """The one line an answered question collapses to."""
    mark = paint("–", "dim", color) if skipped else paint("✔", "green", color)
    return f"{mark} {paint(title, 'bold', color)}  {paint(answer, 'dim' if skipped else 'cyan', color)}\r\n"


def has_keyboard(stream) -> bool:
    """Whether this stream is a terminal we can read one keypress from.

    `isatty` alone is not enough: a stream can claim to be a terminal and have no
    file descriptor to put into raw mode, which is what a captured stdout looks
    like, and `termios` does not exist on Windows.
    """
    try:
        if not stream.isatty():
            return False
        os.fstat(stream.fileno())
    except (AttributeError, OSError, ValueError):
        return False
    if sys.platform == "win32":
        try:
            import msvcrt  # noqa: F401
        except ImportError:
            return False
        return True
    try:
        import termios  # noqa: F401
        import tty  # noqa: F401
    except ImportError:
        return False
    return True


@contextmanager
def raw_mode(stream):
    """Hold the terminal in raw mode for the whole menu, not per keypress.

    Doing it per keypress left the terminal cooked between reads, and that window is
    not theoretical: a key pressed in it was echoed as `^[[B` and then **discarded**,
    because `tty.setraw` defaults to `TCSAFLUSH`, which throws away pending input.
    The menu then waited forever for a key the person had already pressed. Found by
    the pty test, which types faster than any person and hit the window every time.
    """
    if sys.platform == "win32":
        yield                       # msvcrt reads a key without touching modes
        return
    import termios
    import tty

    fd = stream.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd, termios.TCSANOW)     # NOW, not FLUSH: keep what is queued
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _read_key(stream) -> str:
    """One keypress, escape sequence included. The caller holds raw mode."""
    if sys.platform == "win32":
        import msvcrt
        first = msvcrt.getwch()
        if first in ("\x00", "\xe0"):
            return first + msvcrt.getwch()
        return first

    import select

    fd = stream.fileno()
    first = os.read(fd, 1).decode("utf-8", "replace")
    if first != "\x1b":
        return first
    # An escape on its own is a cancel; an escape followed immediately by more
    # bytes is an arrow. The only way to tell them apart is to wait a moment.
    rest = ""
    while len(rest) < 2 and select.select([fd], [], [], 0.05)[0]:
        rest += os.read(fd, 1).decode("utf-8", "replace")
    return first + rest


def _numbered(title: str, note: str, options, multi: bool, default_label: str,
              stdin, out) -> list[str]:
    if title:
        print(f"\n{title}", file=out)
    if note:
        print(note, file=out)
    print("", file=out)
    for i, (_, label, detail) in enumerate(options, 1):
        print(f"  {i}) {label:<14} {detail}".rstrip(), file=out)
    print("", file=out)
    hint = "several allowed, e.g. 1 3" if multi else f"default: {default_label}"
    print(f"Choice ({hint}): ", end="", file=out, flush=True)

    picks = (stdin.readline() or "").split()
    chosen = [options[int(p) - 1][0] for p in picks
              if p.isdigit() and 1 <= int(p) <= len(options)]
    if picks and not chosen:
        print(f"nothing recognised in \"{' '.join(picks)}\"", file=out)
    if not multi:
        return chosen[:1]
    return list(dict.fromkeys(chosen))


def ask(title: str, note: str, options, *, multi: bool = False,
        cursor: int = 0, preselected=(), stdin=None, out=None,
        keyboard: bool | None = None, color: bool | None = None) -> list[str]:
    """Ask one question and return the keys of the chosen options.

    `options` is a list of (key, label, detail). An empty result means the person
    chose nothing, which every caller has to treat as a real answer rather than as
    a failure to answer.
    """
    stdin = stdin or sys.stdin
    out = out or sys.stdout
    if keyboard is None:
        keyboard = has_keyboard(stdin)
    if not keyboard:
        default_label = options[cursor][1] if options else ""
        return _numbered(title, note, options, multi, default_label, stdin, out)
    if color is None:
        color = wants_color(out)

    picked = {i for i, (key, _, _) in enumerate(options) if key in preselected}
    skipped = False
    # The blank line before the question is part of the block that is erased, so
    # that answered questions stack one under the other with no gap.
    question = "\r\n" + render_question(title, note, color)
    rows = len(options) + 2                      # rows, blank, hint
    try:
        # Raw mode first, before a single character of the question is printed. The
        # gap between printing and reading is small and real: a key pressed inside it
        # was echoed onto the screen as `^[[B` and then read as input, so the menu
        # both looked broken and acted on a keystroke twice. Everything printed from
        # here on needs `\r\n`, because raw mode turns off the newline translation.
        with raw_mode(stdin):
            out.write("\x1b[?25l")              # hide the cursor while it moves
            out.write(question)
            out.write(render_list(options, cursor, picked, multi, color))
            out.flush()
            while True:
                key = decode(_read_key(stdin))
                if key == "quit":
                    picked, skipped = set(), True
                    break
                if key == "up":
                    cursor = (cursor - 1) % len(options)
                elif key == "down":
                    cursor = (cursor + 1) % len(options)
                elif key.isdigit() and 1 <= int(key) <= len(options):
                    cursor = int(key) - 1
                    if multi:
                        picked ^= {cursor}
                    else:
                        picked = {cursor}
                        break
                elif key == "space" and multi:
                    picked ^= {cursor}
                elif key == "enter":
                    if not multi:
                        picked = {cursor}
                    break
                out.write(f"\x1b[{rows}A")          # back to the top of the rows
                out.write(render_list(options, cursor, picked, multi, color))
                out.flush()
            # Collapse: back to the blank line above the question, erase everything
            # below it, and leave one line saying what was answered.
            labels = [options[i][1] for i in sorted(picked)]
            answer = "skipped" if skipped else (", ".join(labels) or "nothing")
            out.write(f"\x1b[{question.count(chr(10)) + rows}A\x1b[J")
            out.write(render_answer(title, answer, color, skipped=skipped))
    finally:
        out.write("\x1b[?25h")
        out.flush()

    return [options[i][0] for i in sorted(picked)]


def confirm(question: str, *, stdin=None, out=None, keyboard: bool | None = None,
            color: bool | None = None) -> bool:
    """Yes or no, defaulting to yes, on either input route."""
    stdin = stdin or sys.stdin
    out = out or sys.stdout
    if keyboard is None:
        keyboard = has_keyboard(stdin)
    if not keyboard:
        print(f"{question} [Y/n]: ", end="", file=out, flush=True)
        return (stdin.readline() or "").strip().lower() in ("", "y", "yes")
    if color is None:
        color = wants_color(out)

    with raw_mode(stdin):
        out.write(f"{paint('?', 'cyan', color)} {paint(question, 'bold', color)} "
                  f"{paint('(Y/n)', 'dim', color)} ")
        out.flush()
        while True:
            key = _read_key(stdin)
            if key in ("\r", "\n", "y", "Y"):
                answer = True
                break
            if key in ("n", "N", "\x1b", "\x03"):
                answer = False
                break
    out.write("\r\x1b[2K" + render_answer(question, "yes" if answer else "no", color))
    out.flush()
    return answer



