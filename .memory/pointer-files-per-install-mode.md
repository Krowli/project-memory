---
slug: pointer-files-per-install-mode
title: "The repo's own contract named a script path that did not exist"
kind: bug
created: 2026-08-17
updated: 2026-08-17
sources:
  - CLAUDE.md
  - AGENTS.md
  - install.sh
---

## Cause

`CLAUDE.md`, `AGENTS.md` and `GEMINI.md` all hard-coded
`.agents/skills/project-memory/scripts/memory_search.py`. That path exists in
exactly one install mode — `install.sh --project`. Not in a bare clone, which is
the case `CLAUDE.md` explicitly says it exists for. Not after the default install,
which goes to `~/.agents/skills`. Not after a plugin install.

So the first thing any agent did with the mandated search was fail on ENOENT, and
the contract of this repository had been unexecutable for the whole life of the
project. The evidence was visible from the outside: there was no `.memory/` store
here at all, across fifteen commits of exactly the work the tool says to record,
while the project's durable knowledge sat in a hand-maintained directory beside
it.

## Fix

Each file leads with the path that is correct for its own context — the in-clone
path in `CLAUDE.md`, the default install path in the two files meant to be copied
into other projects — and names the other layouts explicitly at the end.
`SKILL.md` says out loud that its commands are relative to the skill's own
directory, which is the Agent Skills convention but was never stated.

tests/test_pointer_files.py extracts every `python3 ... memory_*.py` command from
the three files and asserts each path either exists in this repository or is the
documented default install location, so this cannot regress silently. The same
file asserts this repository has a store with pages in it.
