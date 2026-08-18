---
slug: fts5-index-is-a-cache
title: "Search keeps an FTS5 index, and it is a cache the search may ignore"
kind: decision
created: 2026-08-17
updated: 2026-08-17
sources:
  - skills/project-memory/scripts/memory_index.py
  - evals/run.py
---

## What the measurement said, and what it did not

The evaluation found the hand-written BM25F and SQLite FTS5 statistically
indistinguishable (nDCG@10 0.644 against 0.646, paired interval across zero). So
the migration buys no quality. It buys speed, and only past a certain size: end to
end as a shell invocation, 235 ms against 99 ms at 90 pages, but 4637 ms against
196 ms at 5000.

The first cost model was wrong in a way worth recording. Timings taken inside the
process made the index look like a win everywhere; the agent actually pays ~30 ms
of interpreter startup on every call, which neither design can remove and which
dominates at small corpus sizes.

## What the migration cost, which was more than expected

"Replace 200 lines of Python with a virtual table" was not the shape of it. Every
one of these is mandatory and each came from a probe rather than a preference:

- No WAL. A WAL database cannot be read from a read-only store and does not work
  over a network filesystem, which is exactly what `--store home` invites.
- The index cannot live in the store: `tracked` mode would commit it, and stores
  created earlier never receive a new `.gitignore` line.
- `import sqlite3` cannot sit at module scope. Debian's `python3-minimal` has no
  `sqlite3` at all, so a top-level import turns a working search into a traceback
  on every session-start hook.
- FTS5's own tokenizers lose NFC normalisation, casefold and identifier splitting,
  all three of which have regression tests. So our tokenizer stays the source of
  truth and its output is what gets indexed — which makes tokenisation part of the
  on-disk format and requires a version stamp that forces a rebuild.
- Freshness needs inode and ctime, not just mtime and size, because `rsync -a` and
  `tar -xp` restore timestamps; and it must compare for equality, because a clock
  that steps backwards makes "newer than the index" serve stale content.
- Twenty concurrent searches onto a cold index produced eleven `database is
  locked` failures until one builder was elected without waiting — and the naive
  version of that fix had nineteen of twenty silently answer from an index still
  being written, which is worse than being slow.

## The rule that makes it safe

The pages are the memory; the index only says which file to open. Every failure —
missing, corrupt, truncated, wrong schema, unreadable, locked, mid-rebuild — falls
through to reading the markdown. `PROJECT_MEMORY_NO_FTS5=1` forces that path, and
CI runs the whole suite twice so it cannot rot on machines that all have FTS5.

Two consequences worth knowing. The two paths are different formulas, so the tail
of the ranking can differ; `--json` reports `served_by` so that is explainable.
And a corrupt index must be *repaired*, not merely survived — answering around it
forever would leave a broken file in the cache and every search paying full price,
working and quietly slow. See [[bm25f-over-hybrid-retrieval]].
