---
slug: wizard-asks-with-arrows-and-scope
title: "The wizard asks with arrows, and asks where it applies"
kind: decision
created: 2026-09-19
updated: 2026-09-19
sources:
  - src/pagelore/menu.py
  - src/pagelore/init.py
---

## Context

The first person to run `lore init` typed a digit at a wall of text and asked why it
was not a normal menu with arrow keys like every other tool they use, and why
choosing "Claude Code" had written into their global config when they wanted one
project. Both questions were fair, and the second was not a preference: the wizard
offered three files, all of them global, and the screen said "applies to every
project" while giving no alternative. That is a notice, not a choice.

The honest part of the answer is that fifteen tests drove those questions and one pty
test proved they were asked at all. Every one of them checked whether the wizard did
the right thing. None of them looked at what using it was like, so "correct" shipped
and "usable" was never measured. [[installed-command-not-copied-directory]] records
the same shape of gap on the packaging side.

## Decision

Three questions, and the first is scope. "This project only" writes into that
repository's own `CLAUDE.md`, `GEMINI.md` or `AGENTS.md`; "every project" writes into
the home-directory ones as before. `--scope project` is the same answer for a script,
and it refuses rather than guessing when there is no repository.

Arrows, space and enter, redrawn in place, on a terminal that can be put into raw
mode. Everywhere else — a pipe, a CI job, a test driving StringIO — the numbered
prompt stays exactly as it was. That split is not a concession: `lore init --agent
claude --yes` runs in scripts, and a wizard that stalls waiting for a keypress that
is never coming is worse than an ugly one. It is also why every existing test of
these questions kept working without being touched.

## The bug the pty test found

Raw mode was entered and left around each individual keypress, leaving the terminal
cooked in between. A key pressed in that window was echoed onto the screen as `^[[B`
and then thrown away, because `tty.setraw` defaults to `TCSAFLUSH`, which discards
queued input. The menu looked broken and then waited forever for a key the person had
already pressed. It reproduced every time under a pty, which types faster than anyone
can, and never once by hand.

Raw mode is now held for the whole question and entered before the question is
printed, which closes the window at both ends. Everything printed inside it carries
`\r\n`, because raw mode turns off the newline translation and a bare line feed walks
the list off to the right.

## Why key handling is a pure function

`menu.decode` takes bytes and returns a name. Terminal behaviour cannot be asserted
from a test with no terminal, and both arrow forms — `ESC [ A` and the application
cursor `ESC O A` — plus the Windows two-byte `\xe0 H` are just byte sequences. So the
table is tested directly and exhaustively, and the two pty tests are left to prove
only the wiring: that a real terminal gets the menu at all, and that a real arrow
moves the cursor.
