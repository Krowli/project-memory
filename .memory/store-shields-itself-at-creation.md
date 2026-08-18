---
slug: store-shields-itself-at-creation
title: "A store that appears on its own appears private"
kind: decision
created: 2026-08-17
updated: 2026-08-17
sources:
  - skills/project-memory/scripts/memory_lib.py
  - install.sh
---

## Context

Installed globally, the skill meets projects it has never seen. A store appears in
each of them at the first write, without anyone setting it up.

## Decision

The store is added to the project's `.gitignore` at the moment it is created, and
only then. That is the one point where nobody has to remember, and the mistake it
prevents is one-way: notes pushed to a remote cannot be unpublished. A store that
already exists is left alone — if the line was removed, that was a decision.
`install.sh --store tracked` writes a `.tracked` marker so the scripts never
quietly ignore a store meant to be committed.

## Consequences

A refusal is often the very first thing that happens in a new project, and a
refusal is logged, so logging has to be able to create and shield the store too.

A search must not. Logging a miss used to create the store and append three lines
to the project's `.gitignore` on the first exploratory query in a repository that
never opted in — a read-only operation dirtying a working tree. The log now takes
an explicit `create` flag, and only the write path passes it.
