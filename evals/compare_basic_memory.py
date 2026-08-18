#!/usr/bin/env python3
"""Optional probe: the closest architectural competitor, on the same corpus.

    python3 -m venv /tmp/bm && /tmp/bm/bin/pip install basic-memory
    BM=/tmp/bm/bin/basic-memory python3 evals/compare_basic_memory.py

Basic Memory is the one system in the field that makes the same core bet as this
skill — markdown files on disk, human-editable, git-friendly — and then adds what
this skill does not have: a persistent hybrid index (SQLite FTS plus local
embeddings) and a real link graph. It needs no API key, so unlike mem0 it can be
measured honestly on a machine with no credentials.

The corpus is written out as a Basic Memory project, indexed with its own
`reindex`, and the identical 270 queries are scored with the identical scorer.
Nothing is tuned on either side.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "skills" / "project-memory" / "scripts"))

import memory_search  # noqa: E402
import run as harness  # noqa: E402

BM = os.environ.get("BM", "basic-memory")
WORKERS = 8


def project(corpus, root: Path) -> Path:
    pages = root / "pages"
    pages.mkdir(parents=True)
    for page in corpus:
        (pages / f"{page['slug']}.md").write_text(
            f"---\ntitle: {page['title']}\ntype: note\n---\n\n{page['body']}\n",
            encoding="utf-8")
    return pages


def main() -> int:
    data = harness.load_corpus()
    corpus, queries = data["pages"], data["known_item"]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pages = project(corpus, root)
        env = dict(os.environ, BASIC_MEMORY_HOME=str(pages), HOME=str(root / "home"))
        (root / "home").mkdir()
        subprocess.run([BM, "project", "add", "zenith", str(pages)],
                       capture_output=True, env=env)
        t = time.perf_counter()
        subprocess.run([BM, "reindex"], capture_output=True, env=env, timeout=1800)
        index_build = time.perf_counter() - t

        def ask(item):
            try:
                proc = subprocess.run([BM, "tool", "search-notes", item["q"]],
                                      capture_output=True, text=True, env=env, timeout=180)
                payload = json.loads(proc.stdout[proc.stdout.index("{"):])
                return [h["permalink"].split("/")[-1] for h in payload.get("results", [])][:10]
            except Exception:
                return None

        t = time.perf_counter()
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            theirs = list(pool.map(ask, queries))
        per_query_wall = (time.perf_counter() - t) / len(queries) * WORKERS

        store = harness.materialise(corpus, root / "ours")
        pairs = [(q, r) for q, r in zip(queries, theirs) if r is not None]
        mine, other, by_type = [], [], {}
        for item, ranked in pairs:
            relevant = set(item["relevant"])
            ours = harness.ndcg_at(
                [p.slug for _, p in memory_search.search(item["q"], store, k=10)], relevant)
            them = harness.ndcg_at(ranked, relevant)
            mine.append(ours)
            other.append(them)
            by_type.setdefault(item.get("type", "other"), []).append((ours, them))

    delta, low, high = harness.paired_delta(mine, other)
    print(f"corpus {len(corpus)} pages | {len(pairs)}/{len(queries)} queries answered")
    print(f"basic-memory index build {index_build:.0f}s | "
          f"~{per_query_wall:.1f}s per query through its CLI\n")
    print(f"  {'':12} {'shipped':>9} {'basic-memory':>14}")
    print(f"  {'overall':12} {statistics.fmean(mine):>9.3f} {statistics.fmean(other):>14.3f}")
    for kind in sorted(by_type):
        a = statistics.fmean(x for x, _ in by_type[kind])
        b = statistics.fmean(y for _, y in by_type[kind])
        print(f"  {kind:12} {a:>9.3f} {b:>14.3f}")
    mark = "significant" if (low > 0 or high < 0) else "not significant"
    print(f"\n  paired difference {delta:+.3f} [{low:+.3f}, {high:+.3f}] {mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
