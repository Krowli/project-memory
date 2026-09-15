"""Search by the file being edited, not only by words.

`sources` is the one field every page must carry and the one field ranking never
read. An agent about to change `src/reports/tax.js` wants the pages written
against that file before any lexical match — and the page's body need not share
a single word with the query, or with the path, for that to be true.
"""
import json

import memory_search
import memory_write

ABOUT_A = ("## Cause\n\nThe reap loop waits on the child before closing the master fd, "
           "so a child that ignores SIGTERM keeps the fd open and waitpid never returns. " * 2)
ABOUT_WEBGL = ("## Cause\n\nwebgl context loss on display sleep: the renderer keeps a "
               "context across sleep and xterm never asks for a new one. " * 2)


def write(store, slug, sources, body, title=None, supersedes=None):
    memory_write.write_page(store, slug, title or slug.replace("-", " "), "bug",
                            sources, body, supersedes)


def slugs(hits):
    return [p.slug for _, p in hits]


def test_a_page_citing_the_file_is_found_with_no_text_match(store):
    write(store, "reap-loop", ["src/pty/reap.ts"], ABOUT_A)
    write(store, "webgl-loss", ["src/terminal/renderer.ts"], ABOUT_WEBGL)
    assert slugs(memory_search.search("", store, touching=["src/pty/reap.ts"])) == ["reap-loop"]


def test_touching_pages_come_before_every_text_hit(store):
    """The page about the file first, however well another page matches the
    words. Score, recency and slug still order the pages within each group."""
    write(store, "reap-loop", ["src/pty/reap.ts"], ABOUT_A)
    write(store, "webgl-loss", ["src/terminal/renderer.ts"], ABOUT_WEBGL)
    hits = memory_search.search("webgl context loss", store, touching=["src/pty/reap.ts"])
    assert slugs(hits) == ["reap-loop", "webgl-loss"]


def test_a_directory_matches_what_is_under_it_and_nothing_beside_it(store):
    write(store, "inside", ["src/terminal/renderer.ts"], ABOUT_WEBGL)
    write(store, "deeper", ["src/terminal/addons/webgl.ts"], ABOUT_WEBGL)
    write(store, "beside", ["src/terminalx/other.ts"], ABOUT_WEBGL)
    hits = memory_search.search("", store, touching=["src/terminal"])
    assert sorted(slugs(hits)) == ["deeper", "inside"]


def test_a_file_does_not_match_its_siblings(store):
    """No automatic widening to the directory: `src/` would match everything."""
    write(store, "a", ["src/a.ts"], ABOUT_A)
    write(store, "b", ["src/b.ts"], ABOUT_A)
    assert slugs(memory_search.search("", store, touching=["src/a.ts"])) == ["a"]


def test_the_path_may_be_given_relative_to_root_or_absolute(store, monkeypatch):
    root = store.parent
    (root / "src").mkdir()
    (root / "src" / "a.ts").write_text("export {}")
    write(store, "a", ["src/a.ts"], ABOUT_A)
    for given in ("src/a.ts", "./src/a.ts", "src//a.ts", str(root / "src" / "a.ts")):
        assert slugs(memory_search.search("", store, touching=[given])) == ["a"], given
    # From a subdirectory, a path relative to the working directory is fine too.
    monkeypatch.chdir(root / "src")
    assert slugs(memory_search.search("", store, touching=["a.ts"])) == ["a"]


def test_a_superseded_touching_page_keeps_its_marker_and_loses_to_its_replacement(store):
    """`--touching` is a preference, not an override of the supersedes guarantee.
    Alone, the old page is returned and says it was replaced — the same contract
    the index path has when the replacement matches nothing. When the
    replacement is in the list at all, it is never below the page it reversed."""
    write(store, "old", ["src/a.ts"], ABOUT_A)
    write(store, "new", ["src/b.ts"], ABOUT_A, supersedes=["old"])
    memory_write.stamp_superseded(store, "old", "new")
    alone = memory_search.search("", store, touching=["src/a.ts"])
    assert slugs(alone) == ["old"]
    assert "superseded by new" in memory_search.format_hit(*alone[0])
    both = memory_search.search("waitpid", store, touching=["src/a.ts"])
    assert slugs(both) == ["new", "old"]


def test_the_result_line_and_the_json_say_which_file_matched(store, capsys):
    write(store, "a", ["src/a.ts"], ABOUT_A)
    hits = memory_search.search("", store, touching=["src/a.ts"])
    assert "touches src/a.ts" in memory_search.format_hit(*hits[0])

    memory_search.main(["--store", str(store), "--touching", "src/a.ts", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["hits"][0]["touching"] == ["src/a.ts"]
    assert out["served_by"] == "scan"  # sources are not in the index; every page is read


def test_the_cli_takes_the_flag_with_or_without_query_words(store, capsys):
    write(store, "a", ["src/a.ts"], ABOUT_A)
    assert memory_search.main(["--store", str(store), "--touching", "src/a.ts"]) == 0
    assert "a  —" in capsys.readouterr().out
    assert memory_search.main(["waitpid", "--store", str(store), "--touching", "src/a.ts"]) == 0
    assert "a  —" in capsys.readouterr().out


def test_the_cli_refuses_to_run_with_neither(store):
    import pytest
    with pytest.raises(SystemExit) as exc:
        memory_search.main(["--store", str(store)])
    assert exc.value.code == 2


def test_without_the_flag_nothing_changes(populated):
    """Opt-in: the ranking every existing number was measured on is untouched."""
    before = slugs(memory_search.search("display sleep", populated))
    after = slugs(memory_search.search("display sleep", populated, touching=[]))
    assert before == after == ["webgl-context-loss"]
