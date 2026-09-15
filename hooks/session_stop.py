#!/usr/bin/env python3
"""Stop hook: remind the agent, once, when it changed things and recorded nothing.

The session-start hook closed "the agent did not know it had a memory". Nothing
closed "the agent knew and did not write": `SKILL.md`'s "write after meaningful
work" is prose, an invitation — the exact shape the start hook exists to
replace. Measured elsewhere on a small task set, an agent told to read and apply
memory wrote no page in ten tasks; pages appeared only where something forced
them. This is the thing that forces them, at the cheapest point: the end of a
turn, with the diff still in front of the agent.

It speaks only when all of these hold — the working tree has MIN_CHANGED_FILES
or more changed files (`git status`, so committed work is invisible to it), the
store's log holds no page written by this session, this session has not been
reminded before — and it speaks as `additionalContext`, which Claude Code
delivers as hook feedback the agent acts on, not as a blocking error. Nothing
stops the agent from answering "nothing to record" in one word.

"This session" is the `session_id` Claude Code hands every hook; the write path
stamps the same id into the log from the environment the Bash tool runs in. A
payload without one gets no reminder: better silent than wrong.

Whatever goes wrong here, it exits 0 with parseable JSON. A hook that stalls
the session it is decorating is far worse than one that misses a turn.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

STORE_DIRNAME = ".memory"
SCRIPTS = "scripts"
# Below this a turn is a typo, a rename, a one-file fix — the work SKILL.md says
# not to record. A feature touches several files; three is where "notable"
# starts, and it is one knob rather than a second one for lines.
MIN_CHANGED_FILES = 3
_SESSION_ID = re.compile(r"[^A-Za-z0-9._-]")


def skill_root() -> Path:
    """The installed skill directory, whichever way it got installed."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidate = Path(plugin_root) / "skills" / "project-memory"
        if candidate.is_dir():
            return candidate
        return Path(plugin_root)
    here = Path(__file__).resolve().parent.parent
    candidate = here / "skills" / "project-memory"
    return candidate if candidate.is_dir() else here


def find_store(start: Path) -> Path | None:
    override = os.environ.get("PROJECT_MEMORY_DIR")
    if override:
        path = Path(override).expanduser()
        return path if path.is_dir() else None
    for directory in [start, *start.parents]:
        if (directory / STORE_DIRNAME).is_dir():
            return directory / STORE_DIRNAME
    return None


def cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "project-memory"


def changed_files(cwd: Path) -> int | None:
    """Files changed in the working tree, or None where there is no git to ask.

    `git status` rather than `git diff`: a new file the agent has not staged is
    the most common shape of unrecorded work, and `diff` does not see it. The
    store's own pages are excluded — in `tracked` mode a write shows up here,
    and the store's output must not look like unrecorded work.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    count = 0
    for line in proc.stdout.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if STORE_DIRNAME in Path(path).parts:
            continue
        count += 1
    return count


def writes_this_session(store: Path, session: str) -> int:
    log = store / ".log.jsonl"
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0
    count = 0
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("event") == "write" \
                and record.get("session") == session:
            count += 1
    return count


def reminder(changed: int) -> str:
    write = skill_root() / SCRIPTS / "memory_write.py"
    return (
        "<project-memory>\n"
        f"This session changed {changed} files and recorded no page. If anything here "
        "was found out beyond the task, reworked, or chosen over an alternative, "
        "write it now:\n"
        f"  python3 {write} --slug <kebab> --title <one line> "
        "--kind decision|bug|concept|howto --source <path> --body -\n"
        "If two pages you read contradict each other, re-run the newer one with "
        "--supersedes <older-slug>. If there is nothing worth keeping, say so in "
        "one word.\n"
        "</project-memory>"
    )


def _record(store: Path | None, **fields) -> None:
    """One log line per turn, so memory_stats can count the sessions that
    changed things and recorded nothing. Only into a store that exists: a hook
    is not a write, and must not create the store a first page would."""
    if store is None:
        return
    try:
        sys.path.insert(0, str(skill_root() / SCRIPTS))
        from memory_lib import log_event
        log_event(store, "stop", **fields)
    except Exception:
        pass


def decide(payload: dict, cwd: Path) -> dict:
    if payload.get("stop_hook_active"):
        return {}
    session = _SESSION_ID.sub("", str(payload.get("session_id") or ""))
    if not session:
        return {}
    changed = changed_files(cwd)
    if changed is None:
        return {}

    store = find_store(cwd)
    writes = writes_this_session(store, session) if store else 0
    marker = cache_root() / "nudged" / session
    notable = changed >= MIN_CHANGED_FILES
    nudge = notable and writes == 0 and not marker.exists()
    _record(store, session=session, changed=changed, writes=writes,
            notable=notable, nudged=nudge)
    if not nudge:
        return {}
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("", encoding="utf-8")
    except OSError:
        pass  # cannot remember having spoken; speaking twice beats never
    return {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": reminder(changed),
        }
    }


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    if not isinstance(payload, dict):
        payload = {}
    cwd = Path(payload.get("cwd") or os.getcwd())
    print(json.dumps(decide(payload, cwd), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("{}")
        sys.exit(0)
