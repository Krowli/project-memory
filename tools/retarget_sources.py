#!/usr/bin/env python3
"""One-shot: repoint `sources:` after the 0.4.0 move, and touch nothing else.

    python3 tools/retarget_sources.py --check   # list what would change
    python3 tools/retarget_sources.py           # rewrite

Why not `lore write --source <new path>`: `write_page` unions sources and never
removes one (`src/pagelore/write.py`). Amending through the command would leave
every page carrying both the live path and the dead one, exit 0, silently — and
`--touching` would over-match on the dead path forever.

Why `updated:` is not bumped: the content did not change on the day this ran. The
date feeds ranking and a reader's judgement of how current a page is; moving a
file is not a reason to claim the thinking was revisited.

One live page is deliberately left with a dead source: `python3-is-not-a-windows-command`
cites `hooks/hooks.json`, and the lesson it carries — that Windows has no `python3`
— has no home in the tree until the npm shim's interpreter list exists. Add that
path here when it does, rather than pointing the page at something adjacent.

Pages already superseded keep their dead sources. Their value is the record of
what was tried, and repointing them at files that never held that decision would
falsify it. Sources are validated at write time only, so a dead one costs nothing
at rest.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORE = REPO / ".memory"

# The move, one line per renamed file. Everything not listed here stayed put.
MOVES = {
    "skills/project-memory/scripts/memory_lib.py": "src/pagelore/lib.py",
    "skills/project-memory/scripts/memory_index.py": "src/pagelore/index.py",
    "skills/project-memory/scripts/memory_search.py": "src/pagelore/search.py",
    "skills/project-memory/scripts/memory_write.py": "src/pagelore/write.py",
    "skills/project-memory/scripts/memory_stats.py": "src/pagelore/stats.py",
    "skills/project-memory/USE.md": "src/pagelore/data/AGENT.md",
    "skills/project-memory/references/retrieval.md": "docs/retrieval.md",
    "skills/project-memory/references/page-format.md": "docs/page-format.md",
    # SKILL.md was deleted rather than renamed: an Agent Skills manifest has no
    # successor. The contract it carried is the block, which does.
    "skills/project-memory/SKILL.md": "src/pagelore/data/AGENT.md",
}

FRONTMATTER = re.compile(r"\A---\n(.*?\n)---\n", re.S)


def retarget(text: str) -> tuple[str, list[tuple[str, str]]]:
    m = FRONTMATTER.match(text)
    if not m:
        return text, []
    block = m.group(1)
    if re.search(r"^status: superseded$", block, re.M):
        return text, []

    changed: list[tuple[str, str]] = []
    seen: set[str] = set()
    out: list[str] = []
    for line in block.splitlines(keepends=True):
        entry = re.match(r"^  - (.+?)\s*$", line)
        if entry and entry.group(1) in MOVES:
            new = MOVES[entry.group(1)]
            changed.append((entry.group(1), new))
            if new in seen:       # the page already cites the target: drop the duplicate
                continue
            line = f"  - {new}\n"
        if entry:
            seen.add(line[4:].strip())
        out.append(line)
    if not changed:
        return text, []
    return text[:m.start(1)] + "".join(out) + text[m.end(1):], changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="report, do not write")
    args = ap.parse_args(argv)

    touched = 0
    resulting: dict[str, str] = {}
    for page in sorted(STORE.glob("*.md")):
        text = page.read_text(encoding="utf-8")
        new, changed = retarget(text)
        resulting[page.name] = new
        if not changed:
            continue
        touched += 1
        print(page.name)
        for old, target in changed:
            print(f"    {old}\n  → {target}")
        if not args.check:
            page.write_text(new, encoding="utf-8")

    # Scanned against the retargeted text, so `--check` reports the state the
    # run would leave behind rather than the one it starts from.
    dead = []
    for name, text in sorted(resulting.items()):
        m = FRONTMATTER.match(text)
        if not m:
            continue
        listed = re.search(r"^sources:\n((?:  - .*\n)+)", m.group(1), re.M)
        for line in (listed.group(1).splitlines() if listed else []):
            source = line.strip()[2:].strip()
            if not (REPO / source).exists():
                dead.append((name, source))

    print(f"\n{touched} page(s) {'would change' if args.check else 'rewritten'}")
    if dead:
        print("left citing a path that does not exist (superseded pages, on purpose):")
        for name, source in dead:
            print(f"    {name}: {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
