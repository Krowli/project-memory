"""`lore uninstall` — take the connection back out.

`pipx uninstall` removes the program and cannot run it, so it knows nothing about
the file this program edited in the user's agent configuration. Without this
command the fenced block survives as an `@include` pointing at a file nothing will
recreate — a dangling include, which produces no error and silently stops the
agent searching. That is the same failure the whole instruction-block design was
chosen to avoid, so leaving it to `pipx` is not an option.

It removes exactly what `lore init` wrote, and says what it deliberately did not:
the pages are the user's, and a program that can delete them by accident is worse
than no uninstaller.
"""
from __future__ import annotations

import argparse
import shutil
import sys

from . import instructions
from .cli import add_version
from .init import AGENTS


def main(argv: list[str] | None = None, *, prog: str = "lore uninstall") -> int:
    ap = argparse.ArgumentParser(prog=prog, description="Disconnect the memory from your agents.")
    add_version(ap)
    ap.add_argument("--yes", action="store_true",
                    help="also remove ~/.project-memory/ (the block, not your pages)")
    args = ap.parse_args(argv)

    removed = False
    for _, target, _ in AGENTS.values():
        if not target.is_file():
            continue
        try:
            old = target.read_text(encoding="utf-8")
            new, changed = instructions.strip_block(old)
            if changed:
                target.write_text(new, encoding="utf-8")
                print(f"removed:   the block in {target}")
                removed = True
        except OSError as exc:
            print(f"skipped:   {target} ({exc})", file=sys.stderr)

    home = instructions.home()
    if args.yes and home.is_dir():
        shutil.rmtree(home, ignore_errors=True)
        print(f"removed:   {home}")
        removed = True
    elif home.is_dir():
        print(f"kept:      {home}  (pass --yes to remove it too)")

    if not removed:
        print("nothing to remove: no block found in any agent's instruction file")

    print("""
Left alone on purpose:
  .memory/ in your projects   your pages — delete a store yourself if you mean to
  anything you wrote yourself   a line you added by hand, or an agent definition

The program itself:  pipx uninstall pagelore   (or: npm uninstall -g pagelore)""")
    return 0
