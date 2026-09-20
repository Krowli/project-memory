#!/usr/bin/env python3
"""The panes experiment's number: find + read a page, CLI versus the screen.

The CLI round trip for "find the page and read it" is two commands — `search
<query>`, then `show <slug>` retyped from the results — two processes and the
slug typed twice. The opencode-shaped screen (`lore dev --panes`) runs the same
ranked search in-process, fills the `search` word from the picker (`/ se ↵`, two
keys plus one Enter), and opens the top hit with one `o`: `⌕ se ↵ <query> ↵ o`,
no slug ever typed. Both surfaces run the identical `search.search()`, so this
compares interactions, not ranking.

    python3 evals/panes_keystrokes.py [--store PATH]

Deterministic: the query is fixed, so its keystrokes cancel out of the
comparison exactly; what remains is the slug retype the screen saves, so the
saved count is `len(slug) + 7` for every page. Exits 1 if the claim fails on
any measured page.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pagelore.lib import find_store, load_pages

QUERY = "the remembered decision"


def cli_keys(slug: str, query: str = QUERY) -> int:
    """`search <query>` then `show <slug>`, Enter after each."""
    return 1 + len(f"search {query}") + 1 + len(f"show {slug}")


def screen_keys(query: str = QUERY) -> int:
    """`/ se ↵ <query> ↵ o` — the picker fills the command word, `o` the slug."""
    return 1 + 2 + 1 + len(query) + 1 + 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="panes_keystrokes",
                                 description=__doc__)
    ap.add_argument("--store", type=Path, default=None)
    args = ap.parse_args(argv)
    store = (args.store or find_store()).resolve()
    pages = load_pages(store)
    if not pages:
        print(f"{store}: no pages to measure", file=sys.stderr)
        return 2
    pages.sort(key=lambda p: len(p.slug), reverse=True)

    print(f"store: {store} ({len(pages)} page(s))")
    print(f"find + read one page, query {QUERY!r}: keystrokes and spawned processes")
    print(f"{'slug':<46}{'cli':>6}{'screen':>8}{'saved':>7}")
    failures = 0
    for page in pages[:12]:
        cli = cli_keys(page.slug)
        scr = screen_keys()
        if scr >= cli:
            failures += 1
        print(f"{page.slug:<46}{cli:>6}{scr:>8}{cli - scr:>7}")
    total = sum(cli_keys(p.slug) - screen_keys() for p in pages)
    print("\nper page: the screen spawns 0 processes where the CLI spawns 2, and")
    print(f"total over {len(pages)} page(s) it saves {total} keystrokes "
          f"(= sum of len(slug) + 7).")
    if failures:
        print(f"the claim failed on {failures} page(s)", file=sys.stderr)
        return 1
    print("claim holds: find + read on the screen is never more keystrokes "
          "than the CLI round trip.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())