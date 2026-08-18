"""Retrieval methods under test, behind one interface.

Every method takes a query and the corpus, and returns slugs best-first. They are
deliberately implemented here rather than imported wholesale, so a baseline stays
a baseline even when the shipped code changes — except for `bm25f`, which IS the
shipped code, imported, so the number measured is the number users get.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "project-memory" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import os  # noqa: E402

import memory_index  # noqa: E402
import memory_search  # noqa: E402


def shipped(query: str, corpus, store: Path) -> list[str]:
    """What an installed skill actually runs: the FTS5 index when it can be used."""
    return [page.slug for _, page in memory_search.search(query, store, k=10)]


def _scan(query: str, store: Path) -> list[str]:
    os.environ[memory_index.DISABLE_ENV] = "1"
    try:
        return [page.slug for _, page in memory_search.search(query, store, k=10)]
    finally:
        os.environ.pop(memory_index.DISABLE_ENV, None)


def fallback_scan(query: str, corpus, store: Path) -> list[str]:
    """The path that answers on a read-only store, during a rebuild, or where
    sqlite3 is missing. Measured separately because it is a different formula."""
    return _scan(query, store)


def scan_no_title_weight(query: str, corpus, store: Path) -> list[str]:
    """Ablation of the parameter the documentation calls the one that matters.
    Runs on the scan path, which is the only one W_TITLE affects."""
    original = memory_search.W_TITLE
    memory_search.W_TITLE = 0.0
    try:
        return _scan(query, store)
    finally:
        memory_search.W_TITLE = original


def term_count(query: str, corpus, store: Path) -> list[str]:
    """What the skill used before BM25F: raw term frequency, no IDF, no saturation,
    no length normalisation. The claimed improvement is measured against this."""
    terms = set(memory_search.tokenize(query))
    scored = []
    for page in corpus:
        tokens = Counter(memory_search.tokenize(f"{page['title']} {page['slug']} {page['body']}"))
        score = sum(tokens[t] for t in terms)
        if score:
            scored.append((score, page["slug"]))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [slug for _, slug in scored[:10]]


def grep_or(query: str, corpus, store: Path) -> list[str]:
    """`grep -rilE 'a|b|c'` — every page containing any query word, in filename
    order. This is what you get with no ranker at all, and the README claims it is
    not an alternative. This is where that claim is either supported or not."""
    terms = set(memory_search.tokenize(query))
    if not terms:
        return []
    hits = []
    for page in corpus:
        text = f"{page['title']} {page['slug']} {page['body']}".casefold()
        if any(re.search(re.escape(t), text) for t in terms):
            hits.append(page["slug"])
    return sorted(hits)[:10]


_FTS_CACHE: dict[int, sqlite3.Connection] = {}


def _fts_connection(corpus) -> sqlite3.Connection:
    key = id(corpus)
    if key not in _FTS_CACHE:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE pages USING fts5(slug, title, body)")
        conn.executemany(
            "INSERT INTO pages (slug, title, body) VALUES (?, ?, ?)",
            [(p["slug"], p["title"], p["body"]) for p in corpus])
        conn.commit()
        _FTS_CACHE[key] = conn
    return _FTS_CACHE[key]


def fts5(query: str, corpus, store: Path) -> list[str]:
    """SQLite FTS5 with its own BM25 — the commodity answer, and the escape hatch
    `references/retrieval.md` names for corpora past ~5000 pages.

    Terms are joined with an explicit OR. FTS5 joins bare terms with an implicit
    AND, so a two-word query silently returns nothing — a real bug that shipped in
    a production system and went unnoticed for months.
    """
    terms = [t for t in set(memory_search.tokenize(query)) if t.isalnum()]
    if not terms:
        return []
    expr = " OR ".join(f'"{t}"' for t in terms)
    conn = _fts_connection(corpus)
    try:
        rows = conn.execute(
            "SELECT slug FROM pages WHERE pages MATCH ? "
            "ORDER BY bm25(pages, 0.0, 5.0, 1.0) LIMIT 10", (expr,)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [r[0] for r in rows]


_PRETOK_CACHE: dict[int, sqlite3.Connection] = {}


def _pretokenised_connection(corpus) -> sqlite3.Connection:
    """FTS5 fed our own token stream instead of raw text.

    The built-in tokenizers lose three behaviours this project has regression
    tests for: NFC normalisation (macOS NFD `ёлка` becomes unfindable), casefold
    (`STRASSE` / `straße`), and compound-identifier splitting (`useAgentStream`).
    Pre-tokenising and letting FTS5 split on whitespace keeps all three, so this
    is the only variant a migration could actually ship.
    """
    key = id(corpus)
    if key not in _PRETOK_CACHE:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE pages USING fts5("
                     "slug UNINDEXED, title, body, "
                     "tokenize=\"unicode61 remove_diacritics 0 tokenchars '_'\")")
        conn.executemany(
            "INSERT INTO pages (slug, title, body) VALUES (?, ?, ?)",
            [(p["slug"],
              " ".join(memory_search.tokenize(f"{p['title']} {p['slug']}")),
              " ".join(memory_search.tokenize(p["body"])))
             for p in corpus])
        conn.commit()
        _PRETOK_CACHE[key] = conn
    return _PRETOK_CACHE[key]


def fts5_our_tokens(query: str, corpus, store: Path) -> list[str]:
    terms = set(memory_search.tokenize(query))
    if not terms:
        return []
    expr = " OR ".join(f'"{t}"' for t in terms)
    conn = _pretokenised_connection(corpus)
    try:
        rows = conn.execute(
            "SELECT slug FROM pages WHERE pages MATCH ? "
            "ORDER BY bm25(pages, 0.0, 5.0, 1.0) LIMIT 10", (expr,)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [r[0] for r in rows]


METHODS = {
    "shipped (fts5 index)": shipped,
    "shipped fallback (scan)": fallback_scan,
    "scan, title weight 0": scan_no_title_weight,
    "term count (previous)": term_count,
    "fts5 on raw text": fts5,
    "grep -rilE (unranked)": grep_or,
}
