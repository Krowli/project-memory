---
slug: stop-hook-reminds-once
title: "A Stop hook reminds a session that changed things and recorded nothing"
kind: decision
created: 2026-09-15
updated: 2026-09-16
status: superseded
superseded_by: scripts-carry-the-contract-not-hooks
sources:
  - hooks/session_stop.py
  - skills/project-memory/scripts/memory_lib.py
  - skills/project-memory/scripts/memory_stats.py
---

## Context

[[session-hook-not-an-invitation]] settled the read side: a skill description
is an invitation the model may decline, so a hook puts the instruction into the
session unasked. The write side was left as prose — "write after meaningful
work" in SKILL.md — which is exactly the shape that page argues against. An
outside experiment on a ten-task set found the same thing from the other end:
an agent told to read and apply its memory wrote nothing in ten tasks, and
pages appeared only where something forced them. Nothing in this project
measured that; the log could not even say how many sessions there were.

## Decision

`hooks/session_stop.py`, a Claude Code `Stop` hook. When a turn ends with
three or more changed files in `git status` (the store's own pages excluded)
and the log holds no page written by this session, it emits
`hookSpecificOutput.additionalContext` with the write command and a line about
`--supersedes` for contradicting pages. Claude Code delivers that as hook
feedback the agent acts on — the conversation continues once, under the same
`stop_hook_active` guard as a block, but it is not shown as an error and
"nothing to record" in one word ends it. It speaks once per session, remembered
by a marker under the cache directory, because every turn ends in a Stop and a
reminder on each one would teach the agent to answer "nothing" without looking.

"This session" is the `session_id` every hook receives; the write path stamps
the same id into every log line from `CLAUDE_CODE_SESSION_ID`, which Claude
Code exports to the Bash tool. That variable is not in the documented
environment, so a record without it is tolerated, and a payload without a
session id gets no reminder — better silent than wrong.

## Rejected

`decision: "block"` — the same continuation, but shown as a hook error and
counted against the eight-block cap; the reminder is not an error. Counting
lines with `git diff --numstat` — it does not see an unstaged new file, the
most common shape of unrecorded work, and it added a second knob. Reading the
transcript to find writes — the start hook injects the write command itself,
so a substring count is never zero. Creating the store to log into it — a hook
is not a write, and a first page is what creates a store.

## How this is judged

Not on evals: the effect is only visible in the log. The hook records one
`stop` line per turn (changed, writes, notable, nudged) and `memory_stats.py`
reports sessions, sessions that changed the tree and recorded nothing,
reminders sent, and writes per session. The bar, set now: after two weeks,
writes per session up and the median page length not down; if the share of
short pages rises instead, the hook is producing pages to make the reminder
stop, and it comes out. Known blind spot: a session that commits everything
shows a clean tree and is never reminded.
