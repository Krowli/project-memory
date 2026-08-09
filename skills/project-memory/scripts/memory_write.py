#!/usr/bin/env python3
"""Create or update a memory page.

Usage:
  python3 memory_write.py --slug SLUG --title TITLE --kind KIND
                          --source PATH [--source PATH ...] --body TEXT|-
                          [--store DIR]

Re-running with the same slug replaces same-header sections and appends new
ones, so repeated calls are safe.

**A page that is not worth keeping is refused, not written.** The refusal exits
non-zero and names the next command, so the correction lands in the agent's own
loop instead of in a rules file it may not read. This is the whole design: in
the corpus this was built against, 104 of 495 pages were auto-generated stubs
averaging 277 bytes, and they took the top two result slots for real queries.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_lib import find_store, log_event

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Kinds are deliberately few. The corpus that motivated this had a `rationale`
# kind produced by an automated scan; it became 23% of all pages and none of it
# was worth reading.
KINDS = ("decision", "bug", "concept", "howto")

# Below this, a page is restating what the source file already says. Tuned to
# the stub population it is meant to exclude (median 277 bytes including
# frontmatter).
MIN_BODY = 200


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


def reject(store: Path, code: str, reason: str, repair: str, slug: str = "") -> int:
    """Refuse the write and record why. Never writes a page.

    `code` is a short stable token rather than prose so refusals can be counted:
    a gate that fires constantly on one code is either a real corpus problem or
    a rule that needs loosening, and you cannot tell which from memory.
    """
    print(f"REJECTED: {reason}", file=sys.stderr)
    print(f"FIX: {repair}", file=sys.stderr)
    log_event(store, "reject", code=code, slug=slug, reason=reason)
    return 1


def resolve_source(src: str, store: Path) -> Path | None:
    """Sources are cited relative to the project root, but the command may run
    from anywhere. Try the store's parent (the project root, since the store is
    <root>/.memory) and then the working directory."""
    for base in (store.parent, Path.cwd()):
        candidate = base / src
        if candidate.exists():
            return candidate
    return Path(src) if Path(src).exists() else None


def validate(slug: str, kind: str, sources: list[str], body: str, store: Path) -> int | None:
    """Return an exit code to refuse the write, or None to let it through."""
    if not SLUG_RE.match(slug):
        return reject(
            store, "bad_slug",
            f"slug {slug!r} is not kebab-case (lowercase letters, digits, single hyphens)",
            "retry with a slug like 'pty-hangs-on-exit'", slug)

    if kind not in KINDS:
        return reject(
            store, "bad_kind",
            f"kind {kind!r} is not one of: {', '.join(KINDS)}",
            "pick the closest kind and retry", slug)

    if not sources:
        return reject(
            store, "no_sources",
            "no --source given; a page with no anchor in the codebase goes stale invisibly",
            f"retry with at least one: --source path/to/file (relative to {store.parent})",
            slug)

    missing = [s for s in sources if resolve_source(s, store) is None]
    if missing:
        return reject(
            store, "source_missing",
            f"these --source paths do not exist: {', '.join(missing)}",
            f"check the paths — they are resolved against {store.parent} and the "
            "working directory — then retry", slug)

    if len(body.strip()) < MIN_BODY:
        return reject(
            store, "body_too_short",
            f"body is {len(body.strip())} characters, minimum is {MIN_BODY} — a page this "
            "short restates what reading the source would already show",
            "write what a future agent could NOT reconstruct from the code (the cause "
            "behind the symptom, the alternative that was rejected and why), then retry",
            slug)

    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write a project memory page.")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--kind", default=None, help=f"one of: {', '.join(KINDS)}")
    ap.add_argument("--source", action="append", default=[],
                    help="file this page is about; repeatable; must exist")
    ap.add_argument("--body", default=None, help="page body, or - to read stdin")
    ap.add_argument("--store", type=Path, default=None)
    args = ap.parse_args(argv)

    store = args.store or find_store()

    body = args.body
    if body == "-":
        body = sys.stdin.read()
    elif body is None:
        # There used to be a default body here reading "## Context / TODO: why
        # this matters." — a stub generator with a friendly face.
        return reject(
            store, "no_body",
            "no --body given",
            "pass --body with the text, or --body - to read it from stdin", args.slug)

    if args.kind is None:
        return reject(
            store, "bad_kind",
            f"no --kind given; one of: {', '.join(KINDS)}",
            "add --kind decision|bug|concept|howto and retry", args.slug)

    refusal = validate(args.slug, args.kind, args.source, body, store)
    if refusal is not None:
        return refusal

    existed = (store / f"{args.slug}.md").exists()
    path = write_page(store, args.slug, args.title, args.kind, args.source, body)
    log_event(store, "write", slug=args.slug, kind=args.kind,
              mode="merge" if existed else "create", chars=len(body.strip()))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
