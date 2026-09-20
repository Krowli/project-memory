---
slug: panes-command-field
title: "A command field runs commands inside the panes, in-process"
kind: decision
created: 2026-09-20
updated: 2026-09-20
status: superseded
superseded_by: panes-opencode-screen
sources:
  - src/pagelore/panes.py
  - src/pagelore/dev.py
  - tests/test_panes.py
  - evals/panes_keystrokes.py
---

## Cause

The two-pane prototype browsed: list or ranked search on the left, a page on the right, and nothing to do with commands unless you quit back to the line editor. The request that kept coming back was not browse — "a TUI like the opencode one" means a place to type commands inside the screen, see the output inside the screen, and still look around. Every command already has one true rendering: what an agent would see from `cli.main`. The screen must not invent a second one.

## Decision

The panes now have an opencode-style command field at the bottom (prompt `lore > `). Typing any key in browse mode opens it — bound browse keys excepted — `/` opens it prefilled with `search `, Enter runs the line, Esc closes it, and the cursor edits live (insert, backspace, arrows, Ctrl-A/E/U). Commands run **in-process** through the same `cli.main` the CLI runs, with stdout and stderr captured into the right pane, so the output, the `FIX:` lines and the exit code are exactly what an agent would see from the same position; a non-zero rc appends the `exit N` line the REPL prints. A `search` run from the field narrows the left pane to its ranked hits and `list` restores it — the results shape the browse, not just a text dump.

Commands that must own the terminal are refused from the field, never half-run: `mcp` (a stdio server), `dev`, `edit` ($EDITOR on that tty), `panes`, and the interactive `init` wizard without `--yes`. `--sandbox` keeps its meaning — the in-process run gets the throwaway store, HOME and cwd, mirroring the REPL's children.

In-process is fidelity, not a shortcut, and it is tested as such: `tests/test_panes.py` compares the field's output for `list` with a real child's, byte for byte. `evals/panes_keystrokes.py` needed no change — `/` prefills `search `, so the measured find+read flow keeps `len(slug) + 10` fewer keystrokes and zero spawns — and every other command from the field adds its own zero-process claim where the line editor spawns one child per line. The review discipline is unchanged: key→State functions stay pure and tested without a terminal; one pty test types commands into the raw screen and asserts the output pane.

[[dev-panes-prototype]] [[dev-console-stdlib-only]]
