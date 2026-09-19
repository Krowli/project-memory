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


def _render(options, cursor: int, picked: set, multi: bool, out) -> None:
    for i, (_, label, detail) in enumerate(options):
        arrow = "❯" if i == cursor else " "
        if multi:
            box = "[x]" if i in picked else "[ ]"
            line = f" {arrow} {box} {label:<14} {detail}"
        else:
            line = f" {arrow} {label:<20} {detail}"
        # `\r\n`, not `\n`: raw mode turns off ONLCR, so a bare line feed drops a
        # line without returning the carriage and the list walks off to the right.
        out.write(f"\x1b[2K{line.rstrip()}\r\n")
    out.flush()


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
        keyboard: bool | None = None) -> list[str]:
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

    keys = "space to toggle, enter to confirm" if multi else "enter to choose"
    picked = {i for i, (key, _, _) in enumerate(options) if key in preselected}
    try:
        # Raw mode first, before a single character of the question is printed. The
        # gap between printing and reading is small and real: a key pressed inside it
        # was echoed onto the screen as `^[[B` and then read as input, so the menu
        # both looked broken and acted on a keystroke twice. Everything printed from
        # here on needs `\r\n`, because raw mode turns off the newline translation.
        with raw_mode(stdin):
            out.write("\x1b[?25l")              # hide the cursor while it moves
            if title:
                out.write(f"\r\n{title}\r\n")
            if note:
                out.write(f"{note}\r\n")
            out.write(f"  ↑↓ {keys}, esc to skip\r\n")
            _render(options, cursor, picked, multi, out)
            while True:
                key = decode(_read_key(stdin))
                if key == "quit":
                    picked = set()
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
                out.write(f"\x1b[{len(options)}A")   # back to the top of the list
                _render(options, cursor, picked, multi, out)
    finally:
        out.write("\x1b[?25h")
        out.flush()

    return [options[i][0] for i in sorted(picked)]


def confirm(question: str, *, stdin=None, out=None, keyboard: bool | None = None) -> bool:
    """Yes or no, defaulting to yes, on either input route."""
    stdin = stdin or sys.stdin
    out = out or sys.stdout
    if keyboard is None:
        keyboard = has_keyboard(stdin)
    if not keyboard:
        print(f"{question} [Y/n]: ", end="", file=out, flush=True)
        return (stdin.readline() or "").strip().lower() in ("", "y", "yes")

    with raw_mode(stdin):
        out.write(f"{question} [Y/n] ")
        out.flush()
        while True:
            key = _read_key(stdin)
            if key in ("\r", "\n", "y", "Y"):
                answer = True
                break
            if key in ("n", "N", "\x1b", "\x03"):
                answer = False
                break
    print("yes" if answer else "no", file=out)
    return answer



