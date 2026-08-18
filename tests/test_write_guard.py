"""The write gate has to be a gate, not a request.

`README.md` says "writes are refused, not requested" and `SKILL.md` tells the
agent not to route around a refusal by writing the markdown file directly. That
instruction was the only thing holding the door: the Write tool bypassed every
rule in the system. This project's own CLAUDE.md says to prefer a hook over
prose for anything that must hold.
"""
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "write_guard.py"


def run(payload, env=None):
    proc = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "{}")


def decision(out):
    return out.get("hookSpecificOutput", {}).get("permissionDecision")


def test_hand_writing_a_page_is_denied(tmp_path):
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / ".memory" / "a-page.md")}})
    assert decision(out) == "deny"
    assert "memory_write.py" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_hand_editing_a_page_is_denied(tmp_path):
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / ".memory" / "a-page.md")}})
    assert decision(out) == "deny"


def test_ordinary_project_files_are_untouched(tmp_path):
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / "src" / "renderer.ts")}})
    assert decision(out) is None


def test_a_file_merely_named_memory_is_untouched(tmp_path):
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / "docs" / "memory.md")}})
    assert decision(out) is None


def test_the_stores_own_bookkeeping_is_untouched(tmp_path):
    """The store's .gitignore and .tracked marker are written by the tooling and
    by install.sh, not by the write gate."""
    for name in (".gitignore", ".tracked"):
        out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
                   "tool_input": {"file_path": str(tmp_path / ".memory" / name)}})
        assert decision(out) is None, name


def test_a_deliberate_hand_edit_can_be_allowed_through(tmp_path):
    """Repairing a page a human broke is legitimate; it just must not be the
    default path. An env var is checkable, unlike a promise in prose."""
    import os
    env = dict(os.environ, PROJECT_MEMORY_ALLOW_HAND_EDIT="1")
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / ".memory" / "a-page.md")}},
              env=env)
    assert decision(out) is None


def test_a_broken_payload_never_blocks_the_session(tmp_path):
    proc = subprocess.run([sys.executable, str(HOOK)], input="not json at all",
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert json.loads(proc.stdout or "{}") == {}


def test_the_hook_is_registered_for_both_events():
    config = json.loads((HOOK.parent / "hooks.json").read_text(encoding="utf-8"))
    events = config["hooks"]
    assert "SessionStart" in events and "PreToolUse" in events
    commands = [h["command"] for entry in events["PreToolUse"] for h in entry["hooks"]]
    assert any("write_guard.py" in c for c in commands)
    matchers = [entry.get("matcher", "") for entry in events["PreToolUse"]]
    assert any("Write" in m and "Edit" in m for m in matchers)


def test_a_page_with_a_shouty_extension_is_denied(tmp_path):
    """The suffix check was case-sensitive, so `.MD` was allowed — and on a
    case-insensitive filesystem writing `page.MD` clobbers `page.md`."""
    for name in ("a-page.MD", "a-page.Md", "a-page.markdown", "a-page"):
        out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
                   "tool_input": {"file_path": str(tmp_path / ".memory" / name)}})
        assert decision(out) == "deny", name


def test_the_home_store_mode_is_guarded_too(tmp_path):
    """`install.sh --store home` keeps pages in ~/.project-memory/<project>/, a
    path with no `.memory` component in it at all — so the whole documented mode
    was unguarded."""
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(Path.home() / ".project-memory" / "proj" / "p.md")}})
    assert decision(out) == "deny"


def test_a_path_that_only_passes_through_the_store_is_not_blocked(tmp_path):
    """`.memory/../src/x.ts` is a source file. Blocking it was pure obstruction."""
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": str(tmp_path / ".memory" / ".." / "src" / "x.ts")}})
    assert decision(out) is None


def test_a_relative_path_is_resolved_against_cwd(tmp_path):
    out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
               "tool_input": {"file_path": ".memory/a-page.md"}})
    assert decision(out) == "deny"


def test_the_stores_lock_and_temp_files_are_not_pages(tmp_path):
    for name in (".a-page.md.lock", ".a-page.md.123.tmp"):
        out = run({"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(tmp_path),
                   "tool_input": {"file_path": str(tmp_path / ".memory" / name)}})
        assert decision(out) is None, name
