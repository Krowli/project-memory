"""The session hook is what makes the skill work without being introduced.

A skill description is an invitation the model may decline; a SessionStart hook
is text already in the conversation before the first turn. This is the whole
difference between "tell your agent it has a memory" and it knowing.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "session_start.py"


def run(cwd, env_extra=None):
    import os
    env = {**os.environ, **(env_extra or {})}
    env.pop("PROJECT_MEMORY_DIR", None)
    for k, v in (env_extra or {}).items():
        env[k] = v
    proc = subprocess.run([sys.executable, str(HOOK)], capture_output=True, text=True,
                          cwd=cwd, env=env)
    return proc, json.loads(proc.stdout)


def test_emits_valid_json_with_both_key_shapes(tmp_path):
    """Claude Code reads hookSpecificOutput.additionalContext; Cursor reads the
    snake_case key at the top level."""
    proc, out = run(tmp_path)
    assert proc.returncode == 0
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert out["hookSpecificOutput"]["additionalContext"]
    assert out["additional_context"] == out["hookSpecificOutput"]["additionalContext"]


def test_tells_the_agent_both_verbs(tmp_path):
    _, out = run(tmp_path)
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "memory_search.py" in text
    assert "memory_write.py" in text


def test_reports_an_empty_project_honestly(tmp_path):
    _, out = run(tmp_path)
    assert "no memory store yet" in out["hookSpecificOutput"]["additionalContext"]


def test_counts_the_pages_it_finds(tmp_path):
    store = tmp_path / ".memory"
    store.mkdir()
    for name in ("a", "b", "c"):
        (store / f"{name}.md").write_text("---\ntitle: x\n---\n\nbody")
    _, out = run(tmp_path)
    assert "3 memory page(s)" in out["hookSpecificOutput"]["additionalContext"]


def test_finds_the_store_from_a_subdirectory(tmp_path):
    (tmp_path / ".memory").mkdir()
    (tmp_path / ".memory" / "a.md").write_text("x")
    deep = tmp_path / "src" / "nested"
    deep.mkdir(parents=True)
    _, out = run(deep)
    assert "1 memory page(s)" in out["hookSpecificOutput"]["additionalContext"]


def test_stays_small_enough_to_carry_every_turn(tmp_path):
    """This text is paid for on every turn of every session, so it must stay a
    pointer. The full contract belongs in SKILL.md, which loads on demand."""
    _, out = run(tmp_path)
    assert len(out["hookSpecificOutput"]["additionalContext"]) < 2000


def test_a_broken_environment_does_not_stall_the_session(tmp_path, monkeypatch):
    """Whatever goes wrong, the hook must emit parseable JSON and exit 0 — a
    session that will not start is far worse than one without the reminder."""
    proc, out = run(tmp_path, {"PROJECT_MEMORY_DIR": "/nonexistent/nowhere"})
    assert proc.returncode == 0
    assert isinstance(out, dict)


@pytest.mark.parametrize("rel", ["hooks/hooks.json", "hooks/hooks-cursor.json"])
def test_hook_configs_point_at_the_script_that_exists(rel):
    data = json.loads((REPO / rel).read_text())
    blob = json.dumps(data)
    assert "session_start.py" in blob
    assert HOOK.is_file()


def test_claude_hook_fires_on_resume_paths_too():
    """A session that was cleared or compacted has lost the instruction; without
    these matchers the memory silently stops being used mid-work."""
    data = json.loads((REPO / "hooks" / "hooks.json").read_text())
    matcher = data["hooks"]["SessionStart"][0]["matcher"]
    for event in ("startup", "clear", "compact"):
        assert event in matcher
