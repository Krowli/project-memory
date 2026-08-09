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
  --kind bug --source src/terminal/renderer.ts --body -  <<'EOF'
## Cause

The renderer keeps a WebGL context across display sleep. macOS drops the context
on wake, and xterm.js does not re-request one, so the canvas stays blank while
the buffer keeps updating underneath...
EOF
```

All five arguments are required. `--kind` is one of `decision`, `bug`,
`concept`, `howto`. `--body -` reads the page from stdin.

**The script refuses a page that is not worth keeping**, exits non-zero and
prints a `FIX:` line naming the exact next command. Follow that line — do not
route around it by writing the markdown file directly. Refusals:

- no `--source`, or a `--source` path that does not exist on disk
- a body under 200 characters — at that length a page is restating what reading
  the source already shows
- an unknown `--kind`, or a slug that is not kebab-case

Write the thing a future agent could **not** reconstruct from the code: the
cause behind the symptom, the alternative that was rejected and why, the
constraint that lives outside the repository. Re-running the same slug
section-merges rather than duplicating, so a second call is safe. One topic per
page. Cross-link related pages with `[[other-slug]]`.

## What the store records about itself

Every write, refusal and query is appended to `.memory/.log.jsonl`, and the store
keeps its own `.gitignore` so that file is never committed — it holds real
queries. Read it back with:

```bash
python3 scripts/memory_stats.py            # or --since 2026-08-09, or --json
```

You do not need this during normal work. It exists so that "is this helping?"
can be answered with the refusal rate, the codes it fired on, and the queries
that returned nothing, rather than with an impression.

See `references/page-format.md` for the frontmatter contract and
`references/retrieval.md` for how ranking works and how to tune it.
