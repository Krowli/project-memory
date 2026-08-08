# Retrieval

`memory_search.py` builds a BM25F index over the store on every invocation, scores
every page, drops zero scores and returns the top `k` sorted by score then slug.
There is no persisted index and no server.

## Why BM25F

Chosen by benchmark, not by taste. 110 real agent queries pulled from a production
memory store's call log, pooled top-10 from every candidate method, 3 984
(query, page) pairs graded by hand on a 0/1/2 scale, three judges, inter-judge
kappa 0.69–0.73, bootstrap over queries with 10 000 iterations.

| method | nDCG@10 | 95% CI |
|---|---|---|
| hybrid BM25 + bge-m3 via RRF | 0.788 | [0.759, 0.817] |
| **BM25F (this)** | **0.757** | [0.726, 0.787] |
| dense, chunk-level | 0.696 | [0.659, 0.732] |
| dense, whole-page | 0.683 | [0.644, 0.720] |
| term-count scoring | 0.660 | [0.612, 0.705] |

Two deltas decided it. Term-count → BM25F is **+0.097 [+0.053, +0.144], p=0.0001**
and costs nothing. BM25F → hybrid is **+0.032 [+0.002, +0.061], p=0.041** — an
interval whose lower bound sits two thousandths from zero — and costs a resident
1.2 GB embedding model, ~95 ms added to every query (1.27 s if the model has been
evicted), and 286 s to build the index for 491 pages. The first delta is free and
large; the second is paid and inside the noise.

Dense retrieval is not uniformly better even where it is supposed to win. On the
plural query type — bag-of-keywords, 55% of the real log — it is **−0.113
[−0.163, −0.064], p=0.0001** against BM25F. It gains on conceptual prose
(+0.056, p=0.085, interval crosses zero). Failure mode observed by the judges:
`bge-m3` answers the query `sidecar` with `sidebar-*` pages.

## Parameters

`k1=1.2`, `b=0.75` — textbook. A cross-validated sweep found a different optimum
worth 0.017 nDCG@10, which does not justify carrying tuned constants that were
probably fitted to one corpus's quirks.

`W_TITLE=5.0` is the parameter that matters: raising the title weight from 0 to 5
is worth **+0.069 nDCG@10**, an order of magnitude more than k1 and b combined.

IDF is the Lucene form, `log(1 + (N − df + 0.5) / (df + 0.5))`. The classic
Robertson form goes negative once a term appears in more than half the corpus,
which actively penalises a page for containing the word "the".

Both fields are combined into one pseudo-frequency and saturated **once**
(that is what makes it BM25F rather than two BM25 scores added together —
the additive variant measured 0.024 nDCG@10 worse).

## Tokenization

`\w+` with the Unicode flag, so a mixed Cyrillic/Latin store works. Anything that
replaces this must stay bilingual — a tokenizer that drops non-ASCII silently
loses half of such a store.

Compound identifiers are indexed both whole and in pieces: `useAgentStream`
becomes `useagentstream`, `use`, `agent`, `stream`. Splitting happens before
lowercasing, on `_` and at lower→upper boundaries only, so an all-caps `PTY`
survives intact. This inflates the index ~40% and measured **+0.0997** nDCG on
prose queries against **−0.0101** on identifier lookups — a good trade only
because identifier lookups were 1 query in 154. On a corpus queried mostly by
symbol name, re-measure before keeping it.

No stopword list (−0.0026 quality for −7% index size) and no minimum token length
(monotonically harmful: `pty`, `ws`, `id`, `v2`, `ru` all carry signal).

## Cost, and when to stop using this

Measured on synthetic corpora built by replicating a real 491-page store:

| pages | build (whole index) | query |
|---|---|---|
| 491 | 0.29 s | 0.10 ms |
| 5 401 | 2.76 s | 0.19 ms |
| 50 082 | 25.4 s | 0.93 ms |
| 200 328 | 100.8 s | 3.37 ms |

Query time is never the problem; rebuilding is. **Around 5 000 pages** the
rebuild-everything-per-write model stops being free, and the right move is SQLite
FTS5, where an incremental edit is 0.21 ms flat regardless of corpus size and cold
open is 7 ms. If you do that, note that FTS5 joins bare query terms with implicit
AND — a two-word query then returns nothing. Terms must be joined with explicit
`OR`. This is a real bug that shipped in a production system and went unnoticed
for months.

A plain `grep -r` is not a cheaper alternative at any size: 31 ms at 491 pages,
26.7 s at 200 328.
