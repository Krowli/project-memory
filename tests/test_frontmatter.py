"""Older pages write `sources: [a, b]` inline; newer ones use a block list."""
import memory_lib


def _write(store, text):
    p = store / "p.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_inline_sources_list(store):
    p = _write(store, '---\nslug: p\ntitle: "T"\nsources: [a.ts, b.ts]\n---\n\nbody\n')
    assert memory_lib.parse_page(p).meta["sources"] == ["a.ts", "b.ts"]


def test_block_sources_list(store):
    p = _write(store, '---\nslug: p\ntitle: "T"\nsources:\n  - a.ts\n  - b.ts\n---\n\nbody\n')
    assert memory_lib.parse_page(p).meta["sources"] == ["a.ts", "b.ts"]


def test_page_without_frontmatter(store):
    p = _write(store, "just a body\n")
    page = memory_lib.parse_page(p)
    assert page.slug == "p" and "just a body" in page.body


def test_title_falls_back_to_slug(store):
    p = _write(store, "---\nslug: my-page\n---\n\nbody\n")
    assert memory_lib.parse_page(p).title == "my page"
