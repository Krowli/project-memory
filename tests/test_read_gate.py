"""The write gate, applied where it can be applied everywhere: on read.

`memory_write.py` refuses a page too thin to be worth keeping. A page written
around the script — by hand, by another tool, by an agent whose harness has no
way to deny a Write — skipped that check, and a hook denying such writes exists
on one harness only. So the check runs again in search, which runs on every
harness: a page under the floor is not ranked and is named, so it can be
rewritten through the script; a page with no sources is shown but marked.
"""
import json

import memory_index
import memory_lib
import memory_search
import memory_write
import pytest

LONG = ("The reap loop waits on the child before closing the master fd, so a child "
        "that ignores SIGTERM keeps the fd open and waitpid never returns. " * 3)
STUB = "## Cause\n\nwaitpid never returns.\n"
assert len(STUB.strip()) < memory_lib.MIN_BODY


def by_hand(store, slug, body, sources=("src/a.ts",)):
    lines = ["---", f"slug: {slug}", f'title: "{slug}"', "kind: bug"]
    if sources:
        lines += ["sources:", *[f"  - {s}" for s in sources]]
    (store / f"{slug}.md").write_text("\n".join(lines) + "\n---\n\n" + body, encoding="utf-8")


def slugs(hits):
    return [p.slug for _, p in hits]


@pytest.fixture(params=["index", "scan"])
def path(request, monkeypatch):
    """Both retrieval paths must apply the same gate, or the answer depends on
    whether sqlite3 happened to be available."""
    if request.param == "scan":
        monkeypatch.setenv(memory_index.DISABLE_ENV, "1")
    else:
        monkeypatch.delenv(memory_index.DISABLE_ENV, raising=False)
    return request.param


def test_a_page_under_the_floor_is_not_ranked(store, path):
    memory_write.write_page(store, "real", "waitpid hangs", "bug", ["src/a.ts"],
                            "## Cause\n\n" + LONG)
    by_hand(store, "stub", STUB)
    assert slugs(memory_search.search("waitpid", store)) == ["real"]


def test_the_skipped_page_is_named_so_it_can_be_rewritten(store, path, capsys):
    memory_write.write_page(store, "real", "waitpid hangs", "bug", ["src/a.ts"],
                            "## Cause\n\n" + LONG)
    by_hand(store, "stub", STUB)
    memory_search.main(["waitpid", "--store", str(store)])
    err = capsys.readouterr().err
    assert "stub" in err and str(memory_lib.MIN_BODY) in err and "memory_write.py" in err

    memory_search.main(["waitpid", "--store", str(store), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["skipped"] == ["stub"]
    # An interpreter without FTS5 answers from the scan whatever was asked for.
    assert out["served_by"] == (path if memory_index.fts5_available() else "scan")


def test_a_stub_that_does_not_match_is_not_mentioned(store, path, capsys):
    """The line is about what the query would have shown, not an audit of the
    store — that reconcile pass is the thing this project refuses to build."""
    memory_write.write_page(store, "real", "waitpid hangs", "bug", ["src/a.ts"],
                            "## Cause\n\n" + LONG)
    by_hand(store, "stub", "## Cause\n\nkubernetes.\n")
    memory_search.main(["waitpid", "--store", str(store)])
    assert "skipped" not in capsys.readouterr().err


def test_a_page_with_no_sources_is_shown_and_marked(store, path):
    by_hand(store, "anchorless", "## Cause\n\n" + LONG, sources=())
    hits = memory_search.search("waitpid", store)
    assert slugs(hits) == ["anchorless"]
    assert "⚠ no sources" in memory_search.format_hit(*hits[0])


def test_the_floor_is_the_writers_floor(store, path):
    """One constant, shared: a page the writer would accept is never hidden by
    the reader, and a page the reader hides is one the writer would refuse."""
    assert memory_write.MIN_BODY is memory_lib.MIN_BODY
    body = "## Cause\n\n" + "x" * (memory_lib.MIN_BODY - len("## Cause\n\n"))
    assert len(body.strip()) == memory_lib.MIN_BODY
    by_hand(store, "exactly", body)
    assert slugs(memory_search.search("cause", store)) == ["exactly"]


def test_the_skip_is_logged(store, path):
    by_hand(store, "stub", STUB)
    memory_search.search("waitpid", store)
    records = [json.loads(line) for line in
               (store / memory_lib.LOG_NAME).read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "search"
    assert records[-1]["skipped"] == 1
