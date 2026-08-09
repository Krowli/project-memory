"""Shared helpers: locating the store, parsing pages, recording what happened.
Stdlib only."""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

STORE_ENV = "PROJECT_MEMORY_DIR"
STORE_DIRNAME = ".memory"
LOG_NAME = ".log.jsonl"
# Written by `install.sh --store tracked`: the pages here are meant to be
# committed, so nothing should quietly add them to .gitignore behind the user.
TRACKED_MARKER = ".tracked"


def find_store(start: Path | None = None) -> Path:
    """Locate the memory store: $PROJECT_MEMORY_DIR, else nearest .memory/ upward."""
    override = os.environ.get(STORE_ENV)
    if override:
        return Path(override).expanduser().resolve()
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / STORE_DIRNAME).is_dir():
            return candidate / STORE_DIRNAME
    return cur / STORE_DIRNAME


@dataclass
class Page:
    slug: str
    title: str
    body: str
    path: Path
    meta: dict = field(default_factory=dict)


_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_page(path: Path) -> Page:
    """Parse a memory page. Tolerates both inline `sources: [a, b]` and block lists."""
    raw = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = raw
    m = _FM.match(raw)
    if m:
        body = raw[m.end():]
        key = None
        for line in m.group(1).splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if re.match(r"^\s*-\s+", line) and key:
                meta.setdefault(key, [])
                if isinstance(meta[key], list):
                    meta[key].append(line.split("-", 1)[1].strip().strip("\"'"))
                continue
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                meta[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            elif val:
                meta[key] = val.strip("\"'")
            else:
                meta[key] = []
    slug = str(meta.get("slug") or path.stem)
    title = str(meta.get("title") or slug.replace("-", " "))
    return Page(slug=slug, title=title, body=body, path=path, meta=meta)


def load_pages(store: Path) -> list[Page]:
    if not store.is_dir():
        return []
    return [parse_page(p) for p in sorted(store.rglob("*.md"))]


def ensure_store(store: Path) -> None:
    """Create the store if it is missing, and make a brand-new one private.

    Installed globally, the skill meets projects it has never seen; the first
    write in each of them creates a store. Shielding it at creation is the only
    moment where nobody has to remember to do it — and the mistake it prevents
    (notes pushed to a remote) cannot be undone afterwards.

    Only creation triggers this. A store that already exists is left alone: if
    the line was removed, that was a decision.
    """
    if store.exists():
        return
    store.mkdir(parents=True, exist_ok=True)
    if (store / TRACKED_MARKER).exists():
        return
    try:
        gitignore = store.parent / ".gitignore"
        existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        if any(line.strip().rstrip("/") == store.name for line in existing.splitlines()):
            return
        prefix = "" if (not existing or existing.endswith("\n")) else "\n"
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(f"{prefix}\n# project-memory: notes stay local\n{store.name}/\n")
    except OSError:
        # A read-only checkout should not stop the write; the pages still land.
        pass


def log_event(store: Path, event: str, **fields) -> None:
    """Append one JSON line to the store's log. Never raises.

    Without this there is no way to answer how often the write gate fired and on
    what, except from memory — and a check whose result nobody collects is
    indistinguishable from no check. The log also captures the queries actually
    asked, which is the only honest basis for re-tuning ranking later.

    It holds real queries and slugs, so it is shielded from git inside the store
    rather than relying on the store's own mode.
    """
    try:
        store.mkdir(parents=True, exist_ok=True)
        ignore = store / ".gitignore"
        if not ignore.exists():
            with ignore.open("w", encoding="utf-8") as fh:
                fh.write(f"# holds every query and refusal; never commit it\n{LOG_NAME}\n")
        record = {"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                  "event": event, **fields}
        with (store / LOG_NAME).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Telemetry must never be the reason a write or a search fails.
        pass
