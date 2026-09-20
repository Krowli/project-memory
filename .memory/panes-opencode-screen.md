---
slug: panes-opencode-screen
title: "The screen is opencode-shaped: ask box, transcript and / picker, not a browse"
kind: decision
created: 2026-09-20
updated: 2026-09-20
supersedes:
  - panes-command-field
sources:
  - CHANGELOG.md
  - README.md
  - evals/panes_keystrokes.py
  - src/pagelore/dev.py
  - src/pagelore/panes.py
  - tests/test_panes.py
---

## Cause

The request behind `--panes` came back twice, and both times it was not browse:
"a TUI like the opencode one" — a screen you look at the memory through and type
into, one to one with opencode's own screen. The first pass answered with a
two-pane browser plus a command field, and it still read as a file editor: the
field was invisible until you started typing, the list and preview dominated.
So the layout was reversed into opencode's actual shape, captured from a real
pty of opencode 2.x: first an empty state — a logo, a big "Ask anything…" box,
a hint bar — then, once a command has run, a transcript of turns with the field
shrunk to the bottom line. `/` or ctrl+p opens a command picker that fills the
command word into the field, `o` opens the top hit of the last search (the slug
is never retyped), `↑` walks history, PgUp/PgDn scroll the transcript, `q` is
back to the line editor.

## Measured

The keystroke number moved with the layout and was recomputed by the same
deterministic script rather than re-argued: the picker flow `/ se ↵ <query> ↵ o`
still never retypes the slug, and find + read now saves `len(slug) + 7`
keystrokes instead of `len(slug) + 10` — opening the hit costs one `o` instead
of one Enter, an honest, smaller number. Every command still spawns 0 processes
where the line editor spawns one child per line.

## What did not change

Commands run in-process through the same `cli.main`, and byte-for-byte fidelity
against a real child is still a test. Terminal-owning commands (`mcp`, `dev`,
`edit`, `panes`, the init wizard without --yes) are still refused from the
field. The line editor stays the default, the bare-`lore` probe contract is
untouched, and a pipe driving `--panes` still falls back to the editor.

[[dev-panes-prototype]] [[panes-command-field]] [[dev-console-stdlib-only]]
