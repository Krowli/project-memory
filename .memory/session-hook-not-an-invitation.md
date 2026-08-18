---
slug: session-hook-not-an-invitation
title: "The memory is announced by a hook, not by a skill description"
kind: decision
created: 2026-08-17
updated: 2026-08-17
sources:
  - hooks/session_start.py
  - hooks/hooks.json
---

## Context

A skill description is an invitation the model may or may not accept. In practice
an agent with `AGENTS.md` already in context answered "what do you know about this
project" straight from it and never searched — the file in context is the single
most common reason the search gets skipped.

## Decision

A `SessionStart` hook injects the instruction before the first turn, on startup
and again after a clear, a compact or a resume. The agent does not have to be told
it has a memory; it already knows, and knows how many pages this project has. The
text is deliberately a pointer, around 1.8 KB, because it is re-transmitted with
every request in the session; the full contract lives in `SKILL.md` and loads only
when the skill is actually used.

Written in Python rather than bash because python3 is already required by the
scripts and behaves the same on Linux, macOS and Windows, where a bash hook needs
a `.cmd` shim beside it. It emits both `additionalContext` (Claude Code) and
`additional_context` (Cursor).

## Consequences

Whatever goes wrong, the hook prints parseable JSON and exits 0: a session that
will not start is far worse than one without the reminder. Installed as a plugin
the agent picks up `hooks/hooks.json` itself; installed over `curl` there is no
plugin system, so `install.sh` writes the hook into `settings.json` tagged
`project-memory-session-start` so it can be found and removed.

The same file registers the `PreToolUse` guard described in
[[write-gate-refuses-not-requests]].
