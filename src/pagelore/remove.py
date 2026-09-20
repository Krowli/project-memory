"""`lore rm <slug>` — delete one page, and let the store's log know.

A page deleted with the shell's `rm` vanishes without a trace in the one record
that says what happened to the store, and `stats` then counts a write that led
nowhere. The module is `remove` because `rm` reads as the shell's; the command is
`rm` because that is what a person types.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .cli import add_version
from .lib import find_page, find_store, log_event, refuse_missing


def main(argv: list[str] | None = None, *, prog: str = "lore rm") -> int:
    ap = argparse.ArgumentParser(prog=prog, description="Delete one page of project memory.")
    add_version(ap)
    ap.add_argument("slug", help="as a search result printed it")
    ap.add_argument("--store", type=Path, default=None)
    args = ap.parse_args(argv)
    store = args.store or find_store()

    page = find_page(store, args.slug)
    if page is None:
        return refuse_missing(store, args.slug, prog.split()[0])
    page.path.unlink()
    log_event(store, "remove", slug=page.slug)
    print(f"removed  {page.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
