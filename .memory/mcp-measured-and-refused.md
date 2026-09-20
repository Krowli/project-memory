---
slug: mcp-measured-and-refused
title: "MCP измерен против строки в конфиге и отклонён: он ничего не добавляет"
kind: decision
created: 2026-09-19
updated: 2026-09-20
status: superseded
superseded_by: mcp-offered-as-a-choice
sources:
  - evals/mcp_probe.py
  - evals/acceptance.py
---

## Why it was asked

The CLI was chosen early and never measured against MCP. The argument for MCP
was specific and good: its tool list is put in front of the model by the harness
itself, which is exactly the announcement problem an instruction file solves by
hand. Retrieval quality was never in question — an MCP server here is a wrapper
calling the same `memory_search` and `memory_write` functions, so the ranking
cannot differ. What had to be measured was whether an agent reaches for the
memory more reliably when the tools are in its tool list.

## What was measured

`evals/mcp_probe.py` is a stdio MCP server, stdlib only, exposing the two tools
and calling the CLI's own entry points — the write goes through `memory_write.main`,
so the gate, the refusal codes and the `FIX:` lines are the ones the script
produces rather than a second set that could drift.

`evals/acceptance.py --pointer mcp|include|mcp+include` runs a real Claude Code
session in a throwaway project holding the 90-page corpus, on a task-shaped
prompt that never says "why" — "turn GPU rendering on by default, canvas is
slow" — where the store holds the decision and its reversal. Fifteen runs each,
2026-09-19, counting sessions that searched before answering.

| how the agent learns the memory exists | searched first |
|---|---|
| one `@path` line in the project's CLAUDE.md | 15 / 15 |
| MCP tools, Claude Code's default settings | **0 / 15** |
| MCP tools, `ENABLE_TOOL_SEARCH=false` | 15 / 15 |
| MCP tools plus the `@path` line | 15 / 15 |

## The finding that decided it

The zero is not the model ignoring a visible tool. Claude Code defers MCP tools
behind tool search by default, so they are not in the model's tool list at
session start at all — the single advantage MCP was supposed to have does not
exist out of the box. Caught by asking a session to list its tools, which named
core and deferred tools and no MCP tool, while an explicit call by name worked.

With the deferral off, MCP matches the instruction line exactly. It never beats
it, and added on top of it changes nothing: 15/15 either way.

## Decision

The scripts stay, and MCP is not shipped. It costs a config entry in each
agent's own format against one copied directory, a process per session, and
context for a tool list — and buys, measured, nothing. The probe stays in
`evals/` so the question does not have to be re-argued from opinion.

What would reverse this: a harness that surfaces MCP tools by default and has no
instruction file worth writing into. Re-run the same three arms there.
