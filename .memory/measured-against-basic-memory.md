---
slug: measured-against-basic-memory
title: "Retrieval is indistinguishable from Basic Memory, the closest competitor"
kind: decision
created: 2026-08-18
updated: 2026-08-18
sources:
  - evals/compare_basic_memory.py
---

## Result

Basic Memory 0.22.1 over the same 90 pages, the same 270 queries and the same
scorer: **0.640 against this skill's 0.649, paired difference +0.009 [-0.040,
+0.058] — not significant.** Both at defaults, neither tuned.

It is the fair comparison to make. Basic Memory takes the same core bet — markdown
on disk, human-editable, git-friendly — and adds a persistent hybrid index (SQLite
FTS plus local embeddings) and a real link graph. It needs no API key, which is
also why it is the only one of the thirteen surveyed systems that could be
measured honestly on a machine with no credentials.

## The part worth remembering

The split by query type, not the average. The hybrid system is **better on bare
keywords** (0.830 against 0.792) and **worse on paraphrase** (0.481 against 0.532).

That is the second independent measurement here pointing the same way: adding
embeddings does not automatically buy what embeddings are supposed to buy. The
first was `dense_probe.py`, where dense-only retrieval scored 0.347 on paraphrase
against this skill's 0.532. Whole-document embedding of page-sized text appears to
dilute exactly the signal a reworded query needs.

## What this does not license

One corpus, defaults on both sides, and a query set written against these pages
rather than by either project. Latency is deliberately not claimed: Basic Memory
runs as a long-lived MCP server, and measuring it through a fresh CLI process per
query measures startup and model loading. Its link graph, sync and editing tools
are untouched — this compares retrieval quality and nothing else.

mem0 remains unmeasured because its extraction pipeline needs an LLM key, and a
number produced with a substitute local model could not honestly be called mem0.
See [[hybrid-rejected-on-cost-not-quality]].
