"""Entries in the store that are not ordinary pages.

Everything here was found by an independent audit trying to break the first round
of fixes. Each one either took retrieval down for the whole project or let
something out of the store that was never in it.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import memory_search
import memory_write
import pytest

LONG = ("The reap loop waits on the child before closing the master fd, so a child "
        "that ignores SIGTERM keeps the fd open and waitpid never returns. " * 3)


@pytest.fixture()
def stocked(store):
    memory_write.write_page(store, "real", "WebGL context loss", "bug", [],
                            "## Cause\n\n" + LONG)
    return store


def slugs(store, query="webgl context loss"):
    return [p.slug for _, p in memory_search.search(query, store)]


def test_a_directory_named_like_a_page_is_skipped(stocked):
    (stocked / "notes.md").mkdir()
    assert slugs(stocked) == ["real"]


def test_a_broken_symlink_inside_the_store_is_skipped(stocked):
    (stocked / "old-name.md").symlink_to(stocked / "renamed.md")
    assert slugs(stocked) == ["real"]


def test_a_fifo_named_like_a_page_does_not_hang_the_search(stocked):
    """Opening a FIFO for reading blocks until someone writes to it. This did not
    fail the search, it hung it forever, with no timeout anywhere.

    Run in a subprocess with a timeout on purpose: in-process, a regression here
    would hang the whole suite — and a CI job that never finishes is a worse
    signal than one that fails.
    """
    os.mkfifo(stocked / "pipe.md")
    script = (Path(memory_search.__file__).resolve())
    proc = subprocess.run(
        [sys.executable, str(script), "--store", str(stocked), "webgl", "context", "loss",
         "--json"],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert [hit["slug"] for hit in json.loads(proc.stdout)["hits"]] == ["real"]


def test_an_unreadable_page_does_not_end_the_search(stocked):
    if os.geteuid() == 0:
        pytest.skip("root reads everything")
    blocked = stocked / "blocked.md"
    blocked.write_text("---\nslug: blocked\n---\n\nwebgl context loss\n", encoding="utf-8")
    blocked.chmod(0o000)
    try:
        assert slugs(stocked) == ["real"]
    finally:
        blocked.chmod(0o600)


def test_a_symlink_out_of_the_store_stays_out(stocked):
    secret = stocked.parent / ".env"
    secret.write_text("AWS_SECRET_ACCESS_KEY=hunter2\nDB_PASSWORD=swordfish\n")
    (stocked / "env-notes.md").symlink_to(secret)
    assert memory_search.search("secret access key password swordfish", stocked) == []


def test_a_symlink_inside_the_store_is_still_a_page(stocked):
    """Containment, not paranoia: a link that stays inside the store is fine."""
    (stocked / "alias.md").symlink_to(stocked / "real.md")
    assert "real" in slugs(stocked)


def test_a_read_only_store_is_refused_not_crashed(tmp_path):
    """The agent has to be able to tell 'this page is bad' from 'this disk is'."""
    if os.geteuid() == 0:
        pytest.skip("root writes everywhere")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    store = tmp_path / ".memory"
    store.mkdir()
    store.chmod(0o500)
    try:
        rc = memory_write.main([
            "--store", str(store), "--slug", "p", "--title", "T", "--kind", "bug",
            "--source", "src/real.ts", "--body", "## Cause\n\n" + LONG])
        assert rc == 1
    finally:
        store.chmod(0o700)


def test_an_empty_body_is_refused_rather_than_silently_touching_the_page(store):
    """It merged to a no-op: exit 0, nothing said about what changed, and
    `updated:` bumped on a page nobody edited."""
    (store.parent / "a.ts").write_text("export {}")
    args = ["--store", str(store), "--slug", "p", "--title", "T", "--kind", "bug",
            "--source", "a.ts"]
    assert memory_write.main([*args, "--body", "## Cause\n\n" + LONG]) == 0
    before = (store / "p.md").read_text(encoding="utf-8")
    assert memory_write.main([*args, "--body", "   "]) == 1
    assert (store / "p.md").read_text(encoding="utf-8") == before
