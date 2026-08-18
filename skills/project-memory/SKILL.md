---
name: project-memory
description: Durable project memory as markdown pages on disk. Use before answering any question whose answer describes this project — what it is, what it does, how a subsystem works, why it was built that way, what was decided or rejected ("why did we...", "what did we decide about...", "what do you know about this project") — and before starting work on an unfamiliar part of the codebase. Project instruction files (AGENTS.md, CLAUDE.md, README) already in context are not a substitute. Also use when the user asks to remember something, and after a non-trivial bugfix, refactor, or architectural decision, to write the page.
license: MIT
compatibility: Requires Python 3.11+. No network access and no API keys needed.
metadata:
  repository: https://github.com/Krowli/project-memory
  version: "0.2.0"
---

# Project memory

Markdown pages in `.memory/` are the durable record of decisions, contracts and
bugs for this project. Plain files: greppable, diffable, reviewable in a PR, and
readable by any agent or human without a server.

Commands below are written relative to this skill's own directory — the one this
`SKILL.md` is in. Run them from there, or with that path in front.

## Read before you answer, and before you write code

Search whenever your reply would state something about this project — what it
is, what it does, how a subsystem works, why it looks that way, what was tried
and rejected — and before touching an unfamiliar subsystem:

```bash
python3 scripts/memory_search.py "terminal freeze webgl context lost"
```

Prints the store's absolute path, then one ranked line per hit: `slug — title —
the part of the page that matched — [score] updated`. A page that was replaced by
a later one is marked `⚠ superseded by <slug>`; read the replacement first. Open
a full page with `cat <store>/<slug>.md`, using the path from the header line so
it works from any directory. Two or three searches with different wording beats
one long query.

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

**A result list is not evidence that an answer exists.** Search almost never comes
back empty: any page sharing a word with the query scores above zero, and measured
on the evaluation corpus, the top hit for a question the store genuinely cannot
answer scores the same as for one it can (5.29 against 5.32). Read the hits and
judge them on what they say. When nothing there actually answers the question, say
so plainly rather than dressing up the nearest page, then proceed from the code.

## Write after meaningful work

Record after: an architectural decision, a non-obvious bugfix, a new domain
concept, or a contract change. Skip: typos, reverts, formatting, test-only edits.

```bash
python3 scripts/memory_write.py --slug webgl-context-loss \
  --title "xterm WebGL context loss on display sleep" \
  --kind bug --source src/terminal/renderer.ts --body -  <<'PMEOF'
## Cause

The renderer keeps a WebGL context across display sleep. macOS drops the context
on wake, and xterm.js does not re-request one, so the canvas stays blank while
the buffer keeps updating underneath...
PMEOF
```

`--slug`, `--title`, `--kind`, `--source` and `--body` are all required.
`--kind` is one of `decision`, `bug`, `concept`, `howto`. `--body -` reads the
page from stdin; the terminator is `PMEOF` rather than `EOF` because a page that
documents heredocs otherwise ends its own body early and the rest of the text is
executed by the shell. To pass a long body without a heredoc at all, write it to
a file and use `--body - < page.md`.

**The script refuses a page that is not worth keeping**, exits non-zero and
prints a `FIX:` line naming the exact next command. Follow that line — writing
the markdown file directly is denied by a hook. Refusals:

- no `--source`, or a `--source` path that does not exist on disk
- a resulting page under 200 characters — at that length a page is restating what
  reading the source already shows
- an unknown `--kind`, or a slug that is not kebab-case
- `--supersedes` naming a slug that is not in the store

Write the thing a future agent could **not** reconstruct from the code: the
cause behind the symptom, the alternative that was rejected and why, the
constraint that lives outside the repository. One topic per page; cross-link
related pages with `[[other-slug]]`.

Re-running the same slug replaces same-header sections **in place** and appends
new ones, so a second call is safe and an amendment is cheap — the 200-character
floor is measured against the resulting page, not against what you are adding.
The command prints `replaced:` and `appended:` for every section it touched,
because replacing a section is destructive and the default store has no version
control behind it.

## When a decision is reversed

A reversal recorded as a new page leaves two pages that both read as current, and
ranking cannot tell which is which. Name what is being replaced:

```bash
python3 scripts/memory_write.py --slug auth-jwt-migration \
  --title "Auth moves to JWT" --kind decision --source src/auth/session.ts \
  --supersedes auth-server-sessions --body -  <<'PMEOF'
## Decision
...
PMEOF
```

The old page gets `status: superseded` and `superseded_by:`, is demoted in
ranking, and carries the marker in every result line. It stays searchable — what
was rejected and why is often the useful part — but it stops outranking the page
that replaced it.

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
