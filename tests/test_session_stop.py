"""The write side gets a hook too.

The session-start hook closed "the agent did not know it had a memory". Nothing
closed "the agent knew and did not write": `SKILL.md`'s "write after meaningful
work" is prose, an invitation — the exact shape the start hook exists to
replace. This hook fires when Claude finishes a turn, and speaks only when the
working tree changed and the log holds no page from this session, once per
session, as feedback the agent acts on rather than as an error.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import memory_lib
import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "hooks" / "session_stop.py"


def run(payload, cwd, cache, stdin=None):
    env = {**os.environ, "XDG_CACHE_HOME": str(cache)}
    env.pop("PROJECT_MEMORY_DIR", None)
    proc = subprocess.run([sys.executable, str(HOOK)],
                          input=json.dumps(payload) if stdin is None else stdin,
                          capture_output=True, text=True, cwd=cwd, env=env)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "{}")


def context(out):
    return out.get("hookSpecificOutput", {}).get("additionalContext")


def stop(session="s1", active=False):
    return {"hook_event_name": "Stop", "session_id": session, "stop_hook_active": active}


@pytest.fixture()
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def change(root, n):
    for i in range(n):
        (root / f"file{i}.ts").write_text("export {}")


def test_a_broken_payload_never_blocks_the_session(project, tmp_path):
    assert run({}, project, tmp_path, stdin="not json at all") == {}


def test_silent_when_nothing_changed(project, tmp_path):
    assert run(stop(), project, tmp_path) == {}


def test_silent_below_the_threshold(project, tmp_path):
    change(project, 2)
    assert run(stop(), project, tmp_path) == {}


def test_reminds_when_the_tree_changed_and_nothing_was_recorded(project, tmp_path):
    change(project, 3)
    out = run(stop(), project, tmp_path)
    text = context(out)
    assert out["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert "3 files" in text and "no page" in text
    assert "memory_write.py" in text
    assert "--supersedes" in text
    assert "decision" not in out, "feedback, not a block: the agent may answer in one word"


def test_silent_while_already_continuing_because_of_a_stop_hook(project, tmp_path):
    change(project, 3)
    assert run(stop(active=True), project, tmp_path) == {}


def test_silent_outside_a_git_repository(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    change(root, 5)
    assert run(stop(), root, tmp_path) == {}


def test_silent_without_a_session_to_attribute_writes_to(project, tmp_path):
    change(project, 3)
    assert run({"hook_event_name": "Stop", "stop_hook_active": False}, project, tmp_path) == {}


def test_silent_once_this_session_recorded_a_page(project, tmp_path):
    change(project, 3)
    store = project / ".memory"
    store.mkdir()
    memory_lib.log_event(store, "write", slug="p", session="s1")
    assert run(stop(), project, tmp_path) == {}


def test_a_page_from_another_session_does_not_count(project, tmp_path):
    change(project, 3)
    store = project / ".memory"
    store.mkdir()
    memory_lib.log_event(store, "write", slug="p", session="someone-else")
    assert context(run(stop(), project, tmp_path))


def test_reminds_once_per_session(project, tmp_path):
    """Every turn ends in a Stop. A reminder on each of them is nagging, and
    nagging teaches the agent to answer "nothing" without looking."""
    change(project, 3)
    assert context(run(stop(), project, tmp_path))
    assert run(stop(), project, tmp_path) == {}
    assert context(run(stop(session="s2"), project, tmp_path))


def test_the_stores_own_files_are_not_changed_files(project, tmp_path):
    """A write creates pages, and in `tracked` mode they show up in `git status`.
    Counting them would make the store's own output look like unrecorded work."""
    store = project / ".memory"
    store.mkdir()
    for name in ("a", "b", "c"):
        (store / f"{name}.md").write_text("---\ntitle: x\n---\n\nbody")
    assert run(stop(), project, tmp_path) == {}


def test_records_what_it_saw_when_a_store_exists(project, tmp_path):
    """The measurement the hook exists to enable: sessions that changed things
    and recorded nothing. Without this line in the log, memory_stats has no
    way to count them."""
    change(project, 3)
    store = project / ".memory"
    store.mkdir()
    run(stop(), project, tmp_path)
    (e,) = [json.loads(line) for line in (store / memory_lib.LOG_NAME).read_text().splitlines()
            if line.strip()]
    assert e["event"] == "stop"
    assert (e["session"], e["changed"], e["writes"], e["notable"], e["nudged"]) == \
        ("s1", 3, 0, True, True)


def test_does_not_create_a_store_to_record_into(project, tmp_path):
    """A hook is not a write. The first page creates the store; a reminder that
    no page was written must not."""
    change(project, 3)
    run(stop(), project, tmp_path)
    assert not (project / ".memory").exists()


def test_the_hook_is_registered_for_stop():
    config = json.loads((HOOK.parent / "hooks.json").read_text(encoding="utf-8"))
    commands = [h["command"] for entry in config["hooks"]["Stop"] for h in entry["hooks"]]
    assert any("session_stop.py" in c for c in commands)
    assert HOOK.is_file()
