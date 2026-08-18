"""Ranking has to be protected by something that fails when ranking changes.

`references/retrieval.md` argues the design from a benchmark whose artifacts are
not in this repository. The suite therefore has to carry the invariants that
benchmark bought — otherwise the parameter the document calls the one that
matters can be set to zero and everything stays green.
"""
import unicodedata

import memory_search
import memory_write

DECOY = ("The palette highlights fuzzy match ranges. webgl context loss is mentioned "
         "here in passing, webgl context loss again, and webgl context loss once more. ") * 3


def test_a_title_match_outranks_a_body_repeating_the_query(store):
    """W_TITLE 0 -> 5 was measured at +0.069 nDCG@10 and is the single largest
    lever in the scorer. With the weight at zero the decoy wins on raw term
    frequency, so this test is what makes that number load-bearing."""
    memory_write.write_page(store, "webgl-context-loss",
                            "xterm WebGL context loss on display sleep", "bug", [],
                            "## Cause\n\nThe renderer keeps a context across display sleep.\n")
    memory_write.write_page(store, "command-palette-highlight",
                            "Command palette match highlighting", "concept", [],
                            "## Context\n\n" + DECOY)
    hits = memory_search.search("webgl context loss", store)
    assert next(p.slug for _, p in hits) == "webgl-context-loss"


def test_a_query_finds_a_page_written_in_the_other_unicode_form(store):
    """macOS hands out NFD, most editors write NFC. Unnormalised, `ёлка` split
    into ['е', 'лка'] and matched nothing — zero recall across the boundary, on
    the project's own flagship bilingual claim."""
    memory_write.write_page(store, "nfd-page", unicodedata.normalize("NFD", "Ёлка и йогурт"),
                            "concept", [], unicodedata.normalize("NFD", "## Решение\n\nёлка\n"))
    assert [p.slug for _, p in memory_search.search("ёлка", store)] == ["nfd-page"]
    assert [p.slug for _, p in memory_search.search("йогурт", store)] == ["nfd-page"]


def test_case_folding_covers_more_than_lowercasing(store):
    memory_write.write_page(store, "strasse", "Straße naming", "concept", [],
                            "## Context\n\nDie STRASSE ist lang.\n")
    assert [p.slug for _, p in memory_search.search("straße", store)] == ["strasse"]


def test_the_snippet_shows_the_part_that_matched(store):
    """A fixed first-100-characters prefix made ten hits render as ten identical
    section headers, so the ranking work was invisible and the agent had to cat
    every candidate to triage the list."""
    memory_write.write_page(
        store, "p", "Terminal notes", "concept", [],
        "## Context\n\n" + ("filler sentence that carries no signal at all. " * 12)
        + "\n\nThe pty hangs on exit because waitpid never returns.\n")
    hits = memory_search.search("waitpid hangs", store)
    assert "waitpid" in memory_search.snippet(hits[0][1], query="waitpid hangs")


def test_the_more_recently_updated_page_breaks_a_tie(store):
    """Alphabetical order by slug was the tie-break, so which of two equally
    scored pages came first was decided by its name."""
    memory_write.write_page(store, "zzz-newer", "Retry policy", "decision", [],
                            "## Decision\n\nRetry twice with jitter.\n")
    memory_write.write_page(store, "aaa-older", "Retry policy", "decision", [],
                            "## Decision\n\nRetry twice with jitter.\n")
    page = store / "aaa-older.md"
    page.write_text(page.read_text(encoding="utf-8").replace("updated: 2", "updated: 1"),
                    encoding="utf-8")
    hits = memory_search.search("retry policy", store)
    assert next(p.slug for _, p in hits) == "zzz-newer"


def test_an_empty_store_and_an_empty_query_stay_quiet(store):
    assert memory_search.search("", store) == []
    assert memory_search.search("anything", store) == []
