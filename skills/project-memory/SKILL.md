---
name: project-memory
description: Durable project memory as markdown pages on disk. Use when the user asks to remember a decision, record why something was built a certain way, look up prior context ("why did we...", "what did we decide about..."), or when starting work on an unfamiliar part of a codebase and past decisions would help. Also use after a non-trivial bugfix, refactor, or architectural decision to write the page.
license: MIT
compatibility: Requires Python 3.11+. No network access and no API keys needed.
metadata:
  repository: https://github.com/Krowli/project-memory
  version: "0.1.0"
---

# Project memory

Markdown pages in `.memory/` are the durable record of decisions, contracts and
bugs for this project. Plain files: greppable, diffable, reviewable in a PR, and
readable by any agent or human without a server.

## Read before you write code

Search before answering any "why", "what did we decide", or "how does X work"
question, and before touching an unfamiliar subsystem:

```bash
python3 scripts/memory_search.py "terminal freeze webgl context lost"
```

Prints ranked `slug — title — one-line snippet`. Read the full page with
`cat .memory/<slug>.md` when a hit looks relevant. Two or three searches with
different wording beats one long query.

If search returns nothing relevant, say so plainly rather than inventing an
answer, then proceed from the code.

## Write after meaningful work

Record after: an architectural decision, a non-obvious bugfix, a new domain
concept, or a contract change. Skip: typos, reverts, formatting, test-only edits.

```bash
python3 scripts/memory_write.py --slug webgl-context-loss \
  --title "xterm WebGL context loss on display sleep" \
  --kind bug --source src/terminal/renderer.ts
```

The script creates or section-merges the page and rebuilds the index. One topic
per page. Cross-link related pages with `[[other-slug]]`.

See `references/page-format.md` for the frontmatter contract and
`references/retrieval.md` for how ranking works and how to tune it.
