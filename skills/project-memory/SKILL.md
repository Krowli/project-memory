---
name: project-memory
description: Durable project memory as markdown pages on disk. Use before answering any question whose answer describes this project — what it is, what it does, how a subsystem works, why it was built that way, what was decided or rejected ("why did we...", "what did we decide about...", "what do you know about this project") — and before starting work on an unfamiliar part of the codebase. Project instruction files (AGENTS.md, CLAUDE.md, README) already in context are not a substitute. Also use when the user asks to remember something, and after a non-trivial bugfix, refactor, or architectural decision, to write the page.
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

## Read before you answer, and before you write code

Search whenever your reply would state something about this project — what it
is, what it does, how a subsystem works, why it looks that way, what was tried
and rejected — and before touching an unfamiliar subsystem:

```bash
python3 scripts/memory_search.py "terminal freeze webgl context lost"
```

Prints ranked `slug — title — one-line snippet`. Read the full page with
`cat .memory/<slug>.md` when a hit looks relevant. Two or three searches with
different wording beats one long query.

The trigger is the kind of claim you are about to make, not the wording of the
question. "How does X work", "explain the architecture", "what does this app
do" and "what do you know about this project" are all memory questions: the
code shows what is there, the pages say what it is for and what it cost to get
there.

`AGENTS.md`, `CLAUDE.md` and `README.md` do not substitute for the search. They
carry instructions rather than reasons, and they drift — a stale line in an
instruction file reads exactly like a current one, while a memory page is dated
and names the sources it was written against. Having such a file already in
your context is the most common reason this search gets skipped; it is not a
reason to skip it.

Skip the search for mechanical work — running a command, a typo, a rename,
reading a file the user named — and for general programming questions that are
not about this codebase.

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
