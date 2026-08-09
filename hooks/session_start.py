#!/usr/bin/env python3
"""SessionStart hook: put the memory instruction into every session, unasked.

A skill description is an invitation the model may or may not accept. This is
the difference between "tell your agent it has a memory" and it simply knowing.
Superpowers works the same way, and that is why it needs no introduction.

Kept deliberately short — this text is paid for on every single turn. The full
contract lives in SKILL.md and loads only when the skill is actually used.

Written in Python rather than bash because python3 is already required by the
skill and behaves the same on Linux, macOS and Windows, where a bash hook needs
a .cmd shim beside it.

Emits both `additionalContext` (Claude Code) and `additional_context` (Cursor).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPTS = "scripts"


def skill_root() -> Path:
    """The installed skill directory, whichever way it got installed."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidate = Path(plugin_root) / "skills" / "project-memory"
        if candidate.is_dir():
            return candidate
        return Path(plugin_root)
    # hooks/ lives beside skills/ in the repo, and beside scripts/ once installed
    here = Path(__file__).resolve().parent.parent
    candidate = here / "skills" / "project-memory"
    return candidate if candidate.is_dir() else here


def find_store(start: Path) -> Path | None:
    override = os.environ.get("PROJECT_MEMORY_DIR")
    if override:
        path = Path(override).expanduser()
        return path if path.is_dir() else None
    for directory in [start, *start.parents]:
        if (directory / ".memory").is_dir():
            return directory / ".memory"
    return None


def build_context() -> str:
    root = skill_root()
    search = root / SCRIPTS / "memory_search.py"
    write = root / SCRIPTS / "memory_write.py"
    store = find_store(Path.cwd())

    if store is None:
        state = ("This project has no memory store yet; the first write creates one "
                 "and makes it private automatically.")
    else:
        pages = len(list(store.glob("*.md")))
        state = f"This project has {pages} memory page(s) in {store}."

    return (
        "<project-memory>\n"
        "This session has a durable project memory: markdown pages recording why "
        "things are the way they are — decisions, rejected alternatives, and the "
        "causes behind non-obvious bugs. It holds what the code cannot tell you.\n\n"
        f"{state}\n\n"
        "SEARCH IT before exploring unfamiliar code and before answering any "
        '"why…" or "what did we decide…" question. Several words, they are ranked:\n'
        f"  python3 {search} \"terminal freeze webgl context lost\"\n\n"
        "WRITE after solving something non-obvious — a bug whose cause was far from "
        "its symptom, a decision with a rejected alternative, a constraint from "
        "outside the repository:\n"
        f"  python3 {write} --slug <kebab> --title <one line> "
        "--kind decision|bug|concept|howto --source <path> --body -\n\n"
        "The write refuses pages that are not worth keeping (no sources, a source "
        "path that does not exist, a body under 200 characters) and prints a FIX: "
        "line with the next command. Follow it; do not write the file by hand. "
        "Skip recording typos, formatting, reverts and test-only edits.\n\n"
        "Load the `project-memory` skill for the full contract.\n"
        "</project-memory>"
    )


def main() -> int:
    context = build_context()
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        },
        # Cursor reads snake_case at the top level.
        "additional_context": context,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # A hook that fails must not stall the session it is decorating.
        print("{}")
        sys.exit(0)
