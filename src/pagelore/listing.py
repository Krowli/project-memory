"""`lore list` — every page of the store, newest first, with what `ls` cannot show.

`ls .memory` gives filenames. It does not give the kind, the date, or the one
thing a reader most needs before opening a page: that it was superseded and by
what. The module is `listing` because `list` is a builtin; the command is `list`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .cli import add_version
from .lib import find_store, load_pages


def main(argv: list[str] | None = None, *, prog: str = "lore list") -> int:
    ap = argparse.ArgumentParser(prog=prog, description="List the pages of project memory.")
    add_version(ap)
    ap.add_argument("--store", type=Path, default=None)
    args = ap.parse_args(argv)
    store = args.store or find_store()

    pages = load_pages(store)
    if not pages:
        print(f"no pages in {store}", file=sys.stderr)
        return 0
    pages.sort(key=lambda p: (p.updated, p.slug), reverse=True)
    print(f"{len(pages)} page(s) in {store}")
    for page in pages:
        kind = str(page.meta.get("kind") or "")
        row = f"  {page.updated:<10}  {kind:<8}  {page.slug}  —  {page.title}"
        if page.superseded_by:
            row += f"   ⚠ superseded by {page.superseded_by}"
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
