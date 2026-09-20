"""`lore edit <slug>` — open one page in the editor, then check what it left.

Opening the file by hand is the same action with one thing missing: nothing tells
the person that the page they just trimmed fell under the floor search applies,
so from then on it is silently skipped. The editor cannot know the floor. This
command does, and says so as the editor closes.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from .cli import add_version
from .lib import (
    MIN_BODY,
    find_page,
    find_store,
    log_event,
    parse_page,
    read_text,
    refuse_missing,
    too_thin,
)

# What runs when neither $VISUAL nor $EDITOR is set. None means "refuse and say
# which variable to set", which a test uses to reach that branch.
FALLBACK = "notepad" if sys.platform == "win32" else "vi"


def editor_command() -> list[str] | None:
    """`$VISUAL`, else `$EDITOR`, else the platform's fallback, split like a shell."""
    for var in ("VISUAL", "EDITOR"):
        value = os.environ.get(var, "").strip()
        if value:
            return shlex.split(value, posix=sys.platform != "win32")
    return [FALLBACK] if FALLBACK else None


def main(argv: list[str] | None = None, *, prog: str = "lore edit") -> int:
    ap = argparse.ArgumentParser(prog=prog, description="Open one page in your editor.")
    add_version(ap)
    ap.add_argument("slug", help="as a search result printed it")
    ap.add_argument("--store", type=Path, default=None)
    args = ap.parse_args(argv)
    store = args.store or find_store()
    cmd = prog.split()[0]

    page = find_page(store, args.slug)
    if page is None:
        return refuse_missing(store, args.slug, cmd)
    editor = editor_command()
    if editor is None:
        print("no editor to open it with: set $EDITOR (or $VISUAL) to one", file=sys.stderr)
        return 2

    before = read_text(page.path)
    try:
        code = subprocess.call([*editor, str(page.path)])
    except OSError as exc:
        print(f"could not run {editor[0]}: {exc}", file=sys.stderr)
        return 2
    if code != 0:
        print(f"{editor[0]} exited with {code}", file=sys.stderr)

    if read_text(page.path) == before:
        print(f"unchanged  {page.path}")
        return 0
    if too_thin(parse_page(page.path)):
        print(f"⚠ {page.slug} now has under {MIN_BODY} characters of body, so search will "
              f"skip it. Add to it, or rewrite it through `{cmd} write`.", file=sys.stderr)
    log_event(store, "edit", slug=page.slug)
    print(f"edited     {page.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
