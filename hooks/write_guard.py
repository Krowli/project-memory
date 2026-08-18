#!/usr/bin/env python3
"""PreToolUse hook: a memory page is written by the script, or not at all.

`README.md` says "writes are refused, not requested", and the whole argument for
putting the quality check in the write path is that a rule in prose is advisory
while a gate is not. But the gate could be walked around with the ordinary Write
tool, and the only thing stopping that was another sentence of prose — so the
claim was itself a request. This repository's own CLAUDE.md states the rule it
was breaking: prefer a hook over CLAUDE.md for anything that must hold.

Denying is the point, so it names the command to run instead: a refusal that does
not say what to do next teaches the agent to stop recording. A hand edit is
sometimes legitimate — repairing a page someone broke — so there is an explicit
escape hatch, which is checkable in a way that a promise in prose is not:

    PROJECT_MEMORY_ALLOW_HAND_EDIT=1

Emits nothing (an empty object) for everything else. Whatever goes wrong here,
it exits 0 with parseable JSON: a hook that blocks the session it is decorating
is far worse than one that misses a case.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STORE_DIRNAME = ".memory"
HOME_STORE = ".project-memory"
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Update"}

# The store's own bookkeeping is written by the tooling and by install.sh, and
# none of it is a memory page.
BOOKKEEPING = {".gitignore", ".tracked", ".log.jsonl"}
BOOKKEEPING_SUFFIXES = {".lock", ".tmp"}

REASON = (
    "Memory pages are written by the skill's script, which validates them — a page "
    "with no source, an unresolvable source path or a body too thin to be worth "
    "keeping is refused rather than written. Writing the markdown by hand skips "
    "that check, and hand-edited frontmatter is the one input the parser cannot "
    "round-trip.\n"
    "Use instead:\n"
    "  python3 <skill>/scripts/memory_write.py --slug <kebab> --title <one line> "
    "--kind decision|bug|concept|howto --source <path> --body -\n"
    "Re-running the same slug replaces same-header sections and appends new ones, "
    "so use it for amendments too. To repair a page by hand deliberately, set "
    "PROJECT_MEMORY_ALLOW_HAND_EDIT=1."
)


def in_a_store(path: Path) -> bool:
    parts = path.parts
    if STORE_DIRNAME in parts:
        return True
    # `install.sh --store home` keeps the pages in ~/.project-memory/<project>/
    # and symlinks .memory at it, so a path can be a store path with no `.memory`
    # component anywhere in it.
    return HOME_STORE in parts


def targets_a_page(payload: dict) -> bool:
    tool = payload.get("tool_name")
    if tool not in EDIT_TOOLS:
        return False
    tool_input = payload.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw:
        return False

    path = Path(raw)
    if not path.is_absolute():
        path = Path(payload.get("cwd") or ".") / path

    # Normalise `..` textually first: `.memory/../src/x.ts` is a source file, and
    # blocking it was pure obstruction. Then resolve the parent's symlinks, so the
    # home-mode store is reached whichever of its two names is used.
    plain = Path(os.path.normpath(str(path)))
    try:
        resolved = plain.parent.resolve() / plain.name
    except OSError:
        resolved = plain

    if plain.name in BOOKKEEPING or plain.suffix.lower() in BOOKKEEPING_SUFFIXES:
        return False

    # Every file in a store, not only `*.md`: the suffix check was case-sensitive
    # and extension-bound, so `page.MD` sailed through and clobbered `page.md` on
    # a case-insensitive filesystem, and `page` with no extension was free.
    return in_a_store(plain) or in_a_store(resolved)


def decide(payload: dict) -> dict:
    if os.environ.get("PROJECT_MEMORY_ALLOW_HAND_EDIT"):
        return {}
    if not targets_a_page(payload):
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(decide(payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("{}")
        sys.exit(0)
