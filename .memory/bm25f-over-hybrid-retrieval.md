---
slug: bm25f-over-hybrid-retrieval
title: "Lexical BM25F, and why the embedding hybrid was rejected"
kind: decision
created: 2026-08-17
updated: 2026-08-18
status: superseded
superseded_by: hybrid-rejected-on-cost-not-quality
sources:
  - skills/project-memory/references/retrieval.md
  - skills/project-memory/scripts/memory_search.py
---

## Decision

Ranking is BM25F over two fields, title (plus slug) and body, with the title
weighted 5x. No embeddings, no server, no index on disk.

## What was rejected, and by how much

A hybrid of BM25 with bge-m3 via reciprocal rank fusion measured better by 0.032
nDCG@10, with a 95% interval of [+0.002, +0.061] — a lower bound two thousandths
from zero. It costs a resident 1.2 GB model, ~95 ms added to every query, and
286 s to build the index for 491 pages. The first delta this project did take
(term-count scoring to BM25F, +0.097 [+0.053, +0.144]) was free and large. The
second is paid and inside the noise.

Dense retrieval also lost where it was expected to win: on bag-of-keywords
queries, 55% of the real log, it was 0.113 nDCG worse. The judges recorded bge-m3
answering the query `sidecar` with `sidebar-*` pages.

## What would make this wrong

The benchmark's artifacts are not in this repository, so a reader cannot reproduce
any of it, and the corpus was one project's. Published 2026 results on a
comparable note corpus have gone the other way by a wide margin, so the honest
reason to keep BM25F here is that queries in this store share vocabulary with page
titles — not that lexical retrieval is generally better. What protects the
conclusion in code is tests/test_retrieval_quality.py: it fails if the title
weight goes back to zero. Before that test existed, setting the parameter the
document calls the most important one to 0 kept the whole suite green.

## Amendment 2026-08-17: there is an index now

The line above saying "no server, no index on disk" was true when it was written
and is no longer. Ranking is still lexical and still ours, but a persistent SQLite
FTS5 index now answers when it can. It changes nothing about the choice recorded
here — the embedding hybrid is still rejected for the same reason — and it was
taken on speed alone, after the two lexical rankers measured statistically
identical. See [[fts5-index-is-a-cache]].
