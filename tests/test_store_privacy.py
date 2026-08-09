"""A store that appears on its own must appear private.

With a global install the skill is set up once and then meets projects it has
never seen. The first write in each of them creates a store. If that store is
not shielded at the moment it is created, the protection depends on the user
remembering — in a repository they may well publish.
"""
import memory_lib
import memory_write
import pytest

LONG = ("The reap loop waits on the child before closing the master fd, so a child "
        "that ignores SIGTERM keeps the fd open and waitpid never returns. " * 3)


@pytest.fixture()
def project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    return tmp_path


def write(project, slug="a-page"):
    return memory_write.main([
        "--store", str(project / ".memory"), "--slug", slug, "--title", "T",
        "--kind", "bug", "--source", "src/real.ts", "--body", LONG])


def gitignore(project) -> str:
    path = project / ".gitignore"
    return path.read_text() if path.exists() else ""


def test_a_new_store_shields_itself(project):
    assert write(project) == 0
    assert ".memory/" in gitignore(project)


def test_it_works_when_the_project_has_no_gitignore_yet(project):
    assert not (project / ".gitignore").exists()
    write(project)
    assert (project / ".gitignore").is_file()


def test_existing_gitignore_is_appended_to_not_replaced(project):
    (project / ".gitignore").write_text("node_modules/\ndist/\n")
    write(project)
    text = gitignore(project)
    assert "node_modules/" in text and "dist/" in text and ".memory/" in text


def test_the_entry_is_not_added_twice(project):
    write(project, "one")
    write(project, "two")
    assert gitignore(project).count(".memory/") == 1


def test_an_entry_the_user_already_wrote_is_respected(project):
    (project / ".gitignore").write_text(".memory/\n")
    write(project)
    assert gitignore(project).count(".memory/") == 1


def test_a_deliberately_tracked_store_is_left_alone(project):
    """`--store tracked` means the pages are meant to be committed and reviewed;
    silently ignoring them would quietly undo that choice."""
    store = project / ".memory"
    store.mkdir()
    (store / memory_lib.TRACKED_MARKER).write_text("")
    write(project)
    assert ".memory/" not in gitignore(project)


def test_a_refused_write_still_shields_the_store_it_creates(project):
    """The refusal is logged, and logging creates the store. If that path skips
    the shielding, the very first thing a new project does — get something
    refused — leaves an unprotected store behind, and the later successful write
    sees a directory that already exists and leaves it alone."""
    rc = memory_write.main([
        "--store", str(project / ".memory"), "--slug", "too-thin", "--title", "T",
        "--kind", "bug", "--source", "src/real.ts", "--body", "short"])
    assert rc == 1
    assert (project / ".memory").is_dir()
    assert ".memory/" in gitignore(project)


def test_a_search_against_a_missing_store_shields_it_too(project):
    """Searching also logs, and a search usually happens before any write."""
    import memory_search
    memory_search.search("anything at all", project / ".memory")
    if (project / ".memory").exists():
        assert ".memory/" in gitignore(project)


def test_a_store_that_already_existed_is_left_as_is(project):
    """Only creation triggers this. Someone who deleted the line meant it."""
    (project / ".memory").mkdir()
    (project / ".gitignore").write_text("dist/\n")
    write(project)
    assert ".memory/" not in gitignore(project)
