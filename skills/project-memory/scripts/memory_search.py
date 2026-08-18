#!/usr/bin/env python3
"""Search project memory. Prints ranked `slug — title — snippet`.

Usage:  python3 memory_search.py "query words" [-k N] [--store DIR] [--json]

Ranking is BM25F over two fields — title (+ slug) and body. See
references/retrieval.md for how it was chosen, what it was measured against, and
what of that measurement is reproducible from this repository.

Two retrieval paths, one ordering. A persistent SQLite FTS5 index (memory_index)
answers when it can; when it cannot — no FTS5 in this interpreter, a read-only
store, a sibling process rebuilding, a corrupt file — the pages are read and
ranked in process instead. Slower, never stale, never a traceback.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memory_index
from memory_lib import Page, find_store, load_pages, log_event, parse_page

# BM25F parameters. k1/b are the textbook values; a cross-validated sweep moved
# nDCG@10 by 0.017, which does not justify carrying tuned constants. The title
# weight is the one that matters — 0 → 5 is worth +0.069 nDCG@10, and
# tests/test_retrieval_quality.py fails if it is set back to 0.
K1 = 1.2
B = 0.75
W_TITLE = 5.0

# A superseded page is not irrelevant — the agent may need to know what was
# replaced — but it must not outrank the page that replaced it. A flat demotion
# keeps it findable and out of first place. Recency stays a tie-break rather than
# a score term, which is what the published evidence supports.
SUPERSEDED_WEIGHT = 0.5

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


# Turkish dotted capital I casefolds to "i" plus a combining dot above, which
# matches nothing anyone types. Folding then re-normalising and dropping the
# stranded mark makes `İSTANBUL` and `istanbul` the same term.
_COMBINING_DOT = "\u0307"


def _fold(word: str) -> str:
    # The input is already NFC, and casefold only denormalises in the rare cases
    # that produce a stranded mark — so the expensive path is taken almost never.
    folded = word.casefold()
    if _COMBINING_DOT not in folded:
        return folded
    return unicodedata.normalize("NFC", folded).replace(_COMBINING_DOT, "")


def tokenize(text: str) -> list[str]:
    """Lowercased words, plus the pieces of any compound identifier.

    `useAgentStream` indexes as useagentstream + use + agent + stream. That costs
    ~40% more tokens and gains +0.0997 nDCG on prose queries against −0.0101 on
    identifier lookups — worth it, because identifier lookups were 1 query in
    154. No stopword list and no minimum token length: both measured slightly
    negative (`pty`, `ws`, `id`, `v2`, `ru` all carry signal here).

    Normalised to NFC first, because `\\w+` does not match combining marks:
    unnormalised, macOS's NFD `ёлка` tokenised as ['е', 'лка'] and matched
    nothing a normal editor had written. Folded with casefold() rather than
    lower(), which also covers `STRASSE` / `straße`.
    """
    out: list[str] = []
    for word in _WORD.findall(unicodedata.normalize("NFC", text)):
        out.append(_fold(word))
        parts = _identifier_parts(word)
        if len(parts) > 1:
            out.extend(_fold(p) for p in parts)
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
    if idx.pages[i].superseded_by:
        total *= SUPERSEDED_WEIGHT
    return total


def lift_superseders(hits: list[tuple[float, Page]]) -> list[tuple[float, Page]]:
    """Guarantee that a page outranks anything it superseded.

    The score demotion alone does not: a superseded page whose wording happens to
    match the query better still came out on top of its own replacement, which is
    the exact failure this is here to prevent. Measured on a real pair —
    "Auth uses server-side sessions", superseded, scored 0.5 against its
    replacement's 0.4, because the old page's body mentioned both options.

    So the ordering is corrected pairwise rather than by tuning a weight: only the
    two pages that stand in a supersedes relation move, and only relative to each
    other. Everything else keeps its BM25F order.
    """
    ranked = list(hits)
    for _ in range(len(ranked)):
        position = {page.slug: i for i, (_, page) in enumerate(ranked)}
        for i, (_, page) in enumerate(ranked):
            by = page.superseded_by
            if by and position.get(by, -1) > i:
                ranked.insert(i, ranked.pop(position[by]))
                break
        else:
            break
    return ranked


# Which path answered the last search. The two rankers agree on which pages match
# and on the top hit, and the evaluation finds no quality difference between them
# (nDCG@10 0.644 against 0.652, interval across zero) — but they are different
# formulas, so the ORDER OF THE TAIL can differ. Reporting the path is what makes
# a disagreement between two agents in one fan-out explainable rather than spooky.
last_path = "scan"


def order(hits: list[tuple[float, Page]], k: int) -> list[tuple[float, Page]]:
    """The ordering both retrieval paths share, so they never disagree.

    Stable sorts applied in reverse order of precedence: score first, then the
    more recently updated page, then the slug so the order is deterministic.
    Alphabetical order used to decide which of two equally scored pages the agent
    read first, which is how a reversed decision could come out on top of the
    decision that reversed it.
    """
    hits.sort(key=lambda sp: sp[1].slug)
    hits.sort(key=lambda sp: sp[1].updated, reverse=True)
    hits.sort(key=lambda sp: sp[0], reverse=True)
    # Before truncation, so a replacement is not the hit that falls off the end.
    hits = lift_superseders(hits)
    return hits[:k] if k > 0 else []


def _from_index(query: str, store: Path, k: int) -> list[tuple[float, Page]] | None:
    """Ask the FTS5 index, or None to say the caller should read the markdown.

    More candidates than `k` are taken, because the demotion of a superseded page
    happens here rather than in SQL and can change which pages belong in the top
    `k`. The pages themselves are still read from disk: the markdown is the source
    of truth for everything displayed, and the index only says which files to open.
    """
    rows = memory_index.lookup(query, store, max(k * 3, 30), tokenize)
    if rows is None:
        return None
    hits: list[tuple[float, Page]] = []
    for score, slug in rows:
        try:
            page = parse_page(store / f"{slug}.md")
        except OSError:
            continue  # deleted since the index was built; the next search rebuilds
        if page.superseded_by:
            score *= SUPERSEDED_WEIGHT
        hits.append((score, page))
    return order(hits, k)


def _from_scan(query: str, store: Path, k: int) -> list[tuple[float, Page]]:
    """Read every page and rank in process. Slower at every corpus size, and it
    cannot be stale, so it is what every failure of the index falls back to."""
    terms = tokenize(query)
    pages = load_pages(store)
    if not pages:
        return []
    idx = build_index(pages)
    hits = [(s, idx.pages[i]) for i in range(idx.n_docs)
            if (s := score_doc(terms, idx, i)) > 0]
    return order(hits, k)


def search(query: str, store: Path, k: int = 10) -> list[tuple[float, Page]]:
    terms = tokenize(query)
    if not terms:
        return []

    global last_path
    hits = _from_index(query, store, k)
    last_path = "index"
    if hits is None:
        last_path = "scan"
        hits = _from_scan(query, store, k)

    # Logged including the misses: a query that returns nothing is the strongest
    # signal there is, both about the corpus and about ranking. This is the same
    # telemetry that made it possible to benchmark ranking on real queries rather
    # than invented ones. A search never creates the store — a read-only
    # operation must not dirty a working tree that never opted in.
    log_event(store, "search", query=query, hits=len(hits),
              top=hits[0][1].slug if hits else None)
    return hits


def snippet(page: Page, width: int = 140, query: str = "") -> str:
    """The part of the page that matched, not its first line.

    A fixed prefix made ten hits render as ten identical section headers, because
    the page conventions push every page to open with `## Cause` or `## Decision`
    — so the ranking work was invisible and the agent had to read every candidate
    to triage the list.
    """
    text = " ".join(page.body.split())
    start = 0
    if query:
        # Offsets must come from the raw string. Computing them on a casefolded
        # copy and slicing the original shifts the window off the match, because
        # folding is not length-preserving (ß casefolds to ss).
        positions: list[int] = []
        for term in set(tokenize(query)):
            match = re.search(re.escape(term), text, re.IGNORECASE)
            if match:
                positions.append(match.start())
        if positions:
            # Anchor where the most query terms fall inside one window, not at the
            # earliest match: a query whose first word appears in every page's
            # opening line gave every hit the same generic prefix, which is the
            # failure the fixed prefix had in the first place.
            best = max(positions,
                       key=lambda p: (sum(1 for q in positions if p - 30 <= q < p - 30 + width),
                                      -p))
            start = max(0, best - 30)
    end = start + width
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def format_hit(score: float, page: Page, query: str = "") -> str:
    line = (f"{page.slug}  —  {page.title}  —  {snippet(page, query=query)}   "
            f"[{score:.1f}] {page.updated}")
    if page.superseded_by:
        line += f"  ⚠ superseded by {page.superseded_by}"
    return line


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Search project memory.")
    ap.add_argument("query", nargs="+")
    ap.add_argument("-k", type=int, default=10, help="max results (default 10)")
    ap.add_argument("--store", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    store = args.store or find_store()
    query = " ".join(args.query)
    hits = search(query, store, args.k)

    if args.json:
        print(json.dumps(
            {"served_by": last_path,
             "hits": [{"slug": p.slug, "title": p.title, "score": round(s, 3),
                       "updated": p.updated, "superseded_by": p.superseded_by,
                       "path": str(p.path)} for s, p in hits]},
            ensure_ascii=False, indent=2))
    elif not hits:
        print(f"no matches in {store}", file=sys.stderr)
    else:
        # The store's absolute path, so the documented `cat` works from any
        # working directory rather than only from the store's parent.
        print(f"{len(hits)} hit(s) in {store}")
        for s, p in hits:
            print(format_hit(s, p, query))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
