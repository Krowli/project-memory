"""What the store must tolerate as a directory on a real filesystem.

Each of these was a way one file could take down retrieval for the whole
project, or take something out of it that was never meant to be there.
"""
import memory_lib
import memory_search
import memory_write

LONG = ("The reap loop waits on the child before closing the master fd, so a child "
        "that ignores SIGTERM keeps the fd open and waitpid never returns. " * 3)


def test_one_undecodable_page_does_not_kill_every_search(store):
    """`read_text` without `errors=` raised UnicodeDecodeError, so a single page
    pasted from a Windows-1251 source ended every search in the project with a
    traceback — while writes to other slugs kept succeeding."""
    memory_write.write_page(store, "good", "WebGL context loss", "bug", [], "## Cause\n\n" + LONG)
    (store / "bad.md").write_bytes("---\nslug: bad\n---\n\ncaf\xe9 pty\n".encode("latin-1"))
    hits = memory_search.search("webgl context loss", store)
    assert [p.slug for _, p in hits] == ["good"]


def test_an_archived_page_leaves_the_index(store):
    """`mkdir archive; mv` is the only archive gesture a human has. rglob kept
    the moved page indexed and produced two hits with the same slug, so the
    documented `cat .memory/<slug>.md` silently got the wrong one."""
    memory_write.write_page(store, "retry", "Retry policy", "decision", [], "## Decision\n\n" + LONG)
    archive = store / "archive"
    archive.mkdir()
    (store / "retry.md").rename(archive / "retry.md")
    hits = memory_search.search("retry policy decision", store)
    assert [p.slug for _, p in hits] == []


def test_a_symlinked_page_pointing_outside_the_store_is_ignored(store):
    """`ln -s ../.env .memory/env-notes.md` turned the search the agent runs on
    its own into an exfiltration primitive: the secret was ranked, snippeted to
    stdout, and then `cat`-ed in full."""
    secret = store.parent / ".env"
    secret.write_text("AWS_SECRET_ACCESS_KEY=hunter2\nDB_PASSWORD=hunter2\n")
    (store / "env-notes.md").symlink_to(secret)
    hits = memory_search.search("secret access key password", store)
    assert hits == []


def test_a_search_does_not_create_the_store_it_did_not_find(tmp_path):
    """A read-only operation must not dirty the working tree. Logging a miss used
    to mkdir the store and append three lines to the project's own .gitignore on
    the first exploratory search in a repository that never opted in."""
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    memory_search.search("anything at all", tmp_path / ".memory")
    assert not (tmp_path / ".memory").exists()
    assert (tmp_path / ".gitignore").read_text() == "node_modules/\n"


def test_a_refused_write_still_shields_the_store_it_creates(tmp_path):
    """The write path keeps its side of this: a refusal is often the first thing
    that happens in a new project, and it must not leave an exposed store."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    rc = memory_write.main([
        "--store", str(tmp_path / ".memory"), "--slug", "thin", "--title", "T",
        "--kind", "bug", "--source", "src/real.ts", "--body", "short"])
    assert rc == 1
    assert ".memory/" in (tmp_path / ".gitignore").read_text()


def test_a_dangling_store_symlink_is_refused_not_crashed(tmp_path):
    """`install.sh --store home` symlinks the store. If the target is gone, the
    old code raised a raw FileExistsError instead of a REJECTED/FIX line."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    store = tmp_path / ".memory"
    store.symlink_to(tmp_path / "gone")
    rc = memory_write.main([
        "--store", str(store), "--slug", "p", "--title", "T", "--kind", "bug",
        "--source", "src/real.ts", "--body", "## Cause\n\n" + LONG])
    assert rc == 1


def test_the_gitignore_check_understands_the_anchored_form(tmp_path):
    (tmp_path / ".gitignore").write_text("/.memory/\n")
    memory_lib.ensure_store(tmp_path / ".memory")
    assert (tmp_path / ".gitignore").read_text().count(".memory/") == 1
