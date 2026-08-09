#!/usr/bin/env python3
"""Search project memory. Prints ranked `slug — title — snippet`.

Usage:  python3 memory_search.py "query words" [-k N] [--store DIR] [--json]

Ranking is BM25F over two fields — title (+ slug) and body — chosen by benchmark
against 110 real agent queries with hand-graded relevance. Beat the previous
term-count scorer by +0.097 nDCG@10 (95% CI [+0.053, +0.144]). A hybrid with
bge-m3 embeddings scored +0.032 higher still, but its interval [+0.002, +0.061]
touches zero and it costs a resident 1.2 GB model plus ~95 ms per query, so it is
not here. Details in references/retrieval.md.

There is no persisted index: the whole thing is rebuilt per invocation, which
measured ~0.3 s at 500 pages and 2.8 s at 5 000. Past roughly 5 000 pages that
stops being free and SQLite FTS5 becomes the right answer instead.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_lib import Page, find_store, load_pages, log_event

# BM25F parameters. k1/b are the textbook values; a cross-validated sweep moved
# nDCG@10 by 0.017, which does not justify carrying tuned constants. The title
# weight is the one that matters — 0 → 5 is worth +0.069 nDCG@10.
K1 = 1.2
B = 0.75
W_TITLE = 5.0

_WORD = re.compile(r"\w+", re.UNICODE)
# Split camelCase only at a lower→upper boundary, so `WorkspaceGrid` yields
# workspace/grid while an all-caps `PTY` stays whole.
_CAMEL = re.compile(r"(?<=[a-zа-яё0-9])(?=[A-ZА-ЯЁ])")


def _identifier_parts(word: str) -> list[str]:
    parts: list[str] = []
    for chunk in word.split("_"):
        if chunk:
            parts.extend(p for p in _CAMEL.split(chunk) if p)
    return parts


def tokenize(text: str) -> list[str]:
    """Lowercased words, plus the pieces of any compound identifier.

    `useAgentStream` indexes as useagentstream + use + agent + stream. That costs
    ~40% more tokens and gains +0.0997 nDCG on prose queries against −0.0101 on
    identifier lookups — worth it, because identifier lookups were 1 query in 154.
    No stopword list and no minimum token length: both measured slightly negative
    (`pty`, `ws`, `id`, `v2`, `ru` all carry signal here).
    """
    out: list[str] = []
    for word in _WORD.findall(text):
        out.append(word.lower())
        parts = _identifier_parts(word)
        if len(parts) > 1:
            out.extend(p.lower() for p in parts)
    return out


@dataclass
class Index:
    pages: list[Page]
    title_tf: list[Counter]
    body_tf: list[Counter]
    title_len: list[int]
    body_len: list[int]
    avg_title: float
    avg_body: float
    df: Counter
    n_docs: int


def build_index(pages: list[Page]) -> Index:
    title_tf = [Counter(tokenize(f"{p.title} {p.slug}")) for p in pages]
    body_tf = [Counter(tokenize(p.body)) for p in pages]
    title_len = [sum(c.values()) for c in title_tf]
    body_len = [sum(c.values()) for c in body_tf]
    n = len(pages)

    df: Counter = Counter()
    for tt, bt in zip(title_tf, body_tf):
        for term in set(tt) | set(bt):
            df[term] += 1

    return Index(
        pages=pages,
        title_tf=title_tf,
        body_tf=body_tf,
        title_len=title_len,
        body_len=body_len,
        avg_title=(sum(title_len) / n) if n else 1.0,
        avg_body=(sum(body_len) / n) if n else 1.0,
        df=df,
        n_docs=n,
    )


def _idf(df: int, n_docs: int) -> float:
    """Lucene IDF. The classic Robertson form goes negative once a term is in more
    than half the corpus, which penalises a page for containing the word 'the'."""
    return math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))


def score_doc(terms: list[str], idx: Index, i: int) -> float:
    """BM25F: one saturation over the weighted sum of both fields.

    Summing two independent BM25 scores instead measured 0.024 nDCG worse.
    """
    norm_t = 1.0 - B + B * (idx.title_len[i] / idx.avg_title if idx.avg_title else 1.0)
    norm_b = 1.0 - B + B * (idx.body_len[i] / idx.avg_body if idx.avg_body else 1.0)

    total = 0.0
    for term in set(terms):
        df = idx.df.get(term, 0)
        if not df:
            continue
        tf = (
            W_TITLE * idx.title_tf[i].get(term, 0) / norm_t
            + idx.body_tf[i].get(term, 0) / norm_b
        )
        if tf:
            total += _idf(df, idx.n_docs) * tf / (K1 + tf)
    return total


def search(query: str, store: Path, k: int = 10) -> list[tuple[float, Page]]:
    terms = tokenize(query)
    if not terms:
        return []

    pages = load_pages(store)
    hits: list[tuple[float, Page]] = []
    if pages:
        idx = build_index(pages)
        hits = [(s, idx.pages[i]) for i in range(idx.n_docs)
                if (s := score_doc(terms, idx, i)) > 0]
        hits.sort(key=lambda sp: (-sp[0], sp[1].slug))
        hits = hits[:k]

    # Logged including the misses: a query that returns nothing is the strongest
    # signal there is, both about the corpus and about ranking. This is the same
    # telemetry that made it possible to benchmark ranking on real queries rather
    # than invented ones.
    log_event(store, "search", query=query, hits=len(hits),
              top=hits[0][1].slug if hits else None)
    return hits


def snippet(page: Page, width: int = 100) -> str:
    text = " ".join(page.body.split())
    return text[:width] + ("…" if len(text) > width else "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Search project memory.")
    ap.add_argument("query", nargs="+")
    ap.add_argument("-k", type=int, default=10, help="max results (default 10)")
    ap.add_argument("--store", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    store = args.store or find_store()
    hits = search(" ".join(args.query), store, args.k)

    if args.json:
        print(json.dumps(
            [{"slug": p.slug, "title": p.title, "score": round(s, 3),
              "path": str(p.path)} for s, p in hits],
            ensure_ascii=False, indent=2))
    elif not hits:
        print(f"no matches in {store}", file=sys.stderr)
    else:
        for s, p in hits:
            print(f"{p.slug}  —  {p.title}  —  {snippet(p)}   [{s:.1f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
