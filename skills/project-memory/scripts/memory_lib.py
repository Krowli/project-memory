"""Shared helpers: locating the store, parsing pages. Stdlib only."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

STORE_ENV = "PROJECT_MEMORY_DIR"
STORE_DIRNAME = ".memory"


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
