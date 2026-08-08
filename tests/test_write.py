import memory_lib
import memory_write
import pytest


def test_creates_page_with_frontmatter(store):
    p = memory_write.write_page(store, "a-slug", "A title", "note", [], "## H\n\nbody\n")
    page = memory_lib.parse_page(p)
    assert page.slug == "a-slug"
    assert page.title == "A title"
    assert page.meta["kind"] == "note"


def test_rejects_bad_slug(store):
    with pytest.raises(ValueError):
        memory_write.write_page(store, "Bad Slug", "t", "note", [], "x")


def test_rerun_replaces_same_section(store):
    memory_write.write_page(store, "s", "t", "note", [], "## Cause\n\nfirst\n")
    p = memory_write.write_page(store, "s", "t", "note", [], "## Cause\n\nsecond\n")
    body = memory_lib.parse_page(p).body
    assert "second" in body and "first" not in body


def test_rerun_appends_new_section(store):
    memory_write.write_page(store, "s", "t", "note", [], "## Cause\n\nfirst\n")
    p = memory_write.write_page(store, "s", "t", "note", [], "## Fix\n\napplied\n")
    body = memory_lib.parse_page(p).body
    assert "first" in body and "applied" in body


def test_sources_accumulate(store):
    memory_write.write_page(store, "s", "t", "note", ["a.ts"], "x")
    p = memory_write.write_page(store, "s", "t", "note", ["b.ts"], "x")
    assert memory_lib.parse_page(p).meta["sources"] == ["a.ts", "b.ts"]
