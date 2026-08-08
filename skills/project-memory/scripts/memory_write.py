#!/usr/bin/env python3
"""Create or update a memory page.

Usage:
  python3 memory_write.py --slug SLUG --title TITLE [--kind KIND]
                          [--source PATH ...] [--body TEXT|-] [--store DIR]

Re-running with the same slug replaces same-header sections and appends new
ones, so repeated calls are safe.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_lib import find_store

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def split_sections(body: str) -> list[tuple[str | None, str]]:
    """Split markdown into (header, chunk) pairs; leading text has header None."""
    out: list[tuple[str | None, str]] = []
    header: str | None = None
    buf: list[str] = []
    for line in body.splitlines(keepends=True):
        if line.startswith("## "):
            out.append((header, "".join(buf)))
            header = line.strip()
            buf = [line]
        else:
            buf.append(line)
    out.append((header, "".join(buf)))
    return out


def merge(old_body: str, new_body: str) -> str:
    old = split_sections(old_body)
    incoming = split_sections(new_body)
    replaced = {h for h, _ in incoming if h}
    kept = [(h, c) for h, c in old if h is None or h not in replaced]
    appended = [(h, c) for h, c in incoming if h]
    lead_in = "".join(c for h, c in incoming if h is None).strip()
    if lead_in and not any(h is None and c.strip() for h, c in kept):
        kept = [(None, lead_in + "\n\n")] + [(h, c) for h, c in kept if h is not None]
    return "".join(c for _, c in kept + appended).rstrip() + "\n"


def write_page(store: Path, slug: str, title: str, kind: str,
               sources: list[str], body: str) -> Path:
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"invalid slug {slug!r}: lowercase letters, digits and single hyphens only")
    store.mkdir(parents=True, exist_ok=True)
    path = store / f"{slug}.md"
    today = _dt.date.today().isoformat()

    if path.exists():
        from memory_lib import parse_page
        existing = parse_page(path)
        body = merge(existing.body, body)
        sources = sorted(set(sources) | set(existing.meta.get("sources") or []))
        created = existing.meta.get("created", today)
    else:
        created = today

    fm = [f"slug: {slug}", f'title: "{title}"', f"kind: {kind}",
          f"created: {created}", f"updated: {today}"]
    if sources:
        fm.append("sources:")
        fm.extend(f"  - {s}" for s in sources)
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body.strip() + "\n",
                    encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write a project memory page.")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--kind", default="note")
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--body", default=None, help="page body, or - to read stdin")
    ap.add_argument("--store", type=Path, default=None)
    args = ap.parse_args(argv)

    body = args.body
    if body == "-":
        body = sys.stdin.read()
    elif body is None:
        body = "## Context\n\nTODO: why this matters.\n"

    store = args.store or find_store()
    path = write_page(store, args.slug, args.title, args.kind, args.source, body)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
