"""Re-running a write must never lose what was already on the page.

`SKILL.md` promises "a second call is safe". Every test here is a way that
promise was broken while the command still exited 0 and printed the page path —
the worst possible shape for a failure, because nothing downstream can see it.
"""
import memory_lib
import memory_write

LONG = ("The reap loop waits on the child before closing the master fd, so a child "
        "that ignores SIGTERM keeps the fd open and waitpid never returns. " * 3)


def body_of(path):
    return memory_lib.parse_page(path).body


def test_a_prose_only_rewrite_is_kept(store):
    """A body with no `## ` header used to become lead-in text and then be
    dropped, because only sections with a header were carried over."""
    memory_write.write_page(store, "s", "t", "concept", ["a.ts"], "first pass at the idea")
    p = memory_write.write_page(store, "s", "t", "concept", ["a.ts"], "second pass, corrected")
    assert "second pass, corrected" in body_of(p)


def test_a_section_inside_a_fence_is_not_a_section(store):
    """The store's own subject is markdown pages, so a page that quotes a page is
    the normal case, not an exotic one. Splitting inside the fence deleted the
    closing fence and everything after it."""
    original = (
        "## Cause\n\nThe renderer keeps a context across display sleep.\n\n"
        "## Format\n\nThe frontmatter contract looks like this:\n\n"
        "```markdown\n## Cause\n\nwhat went wrong\n```\n\n"
        "Keep this sentence.\n\n## Fix\n\nland the fix\n")
    memory_write.write_page(store, "s", "t", "bug", ["a.ts"], original)
    p = memory_write.write_page(store, "s", "t", "bug", ["a.ts"], "## Cause\n\nrewritten\n")
    body = body_of(p)
    assert "rewritten" in body
    # The `## Cause` inside the fence belongs to `## Format` and must survive,
    # together with the fence that closes it and everything after.
    assert "what went wrong" in body
    assert "Keep this sentence." in body
    assert "land the fix" in body
    assert body.count("```") % 2 == 0


def test_a_replaced_section_keeps_its_position(store):
    """Replacing a section used to move it to the end of the page, so a one-line
    amendment read as a whole-file rewrite in `git diff`."""
    memory_write.write_page(
        store, "s", "t", "decision", ["a.ts"],
        "## Context\n\nwhy\n\n## Decision\n\nold\n\n## Consequences\n\nwhat it costs\n")
    p = memory_write.write_page(store, "s", "t", "decision", ["a.ts"], "## Decision\n\nnew\n")
    headers = [h for h, _ in memory_write.split_sections(body_of(p)) if h]
    assert headers == ["## Context", "## Decision", "## Consequences"]


def test_sections_stay_separated_by_a_blank_line(store):
    """The merged file has to be the file `page-format.md` shows."""
    memory_write.write_page(store, "s", "t", "concept", ["a.ts"], "## One\n\nfirst\n")
    p = memory_write.write_page(store, "s", "t", "concept", ["a.ts"], "## Two\n\nsecond\n")
    assert "\n\n## Two" in body_of(p)


def test_an_unknown_frontmatter_key_survives_a_rewrite(store):
    """The write path rebuilt frontmatter from a fixed whitelist, so any field a
    user or a later version added was deleted with exit 0. That silently blocks
    every cheap extension of the format, `supersedes:` included."""
    p = memory_write.write_page(store, "s", "t", "decision", ["a.ts"], "## Decision\n\n" + LONG)
    raw = p.read_text(encoding="utf-8")
    p.write_text(raw.replace("kind: decision", "kind: decision\ntags: [auth, security]"),
                 encoding="utf-8")
    memory_write.write_page(store, "s", "t", "decision", ["a.ts"], "## Decision\n\nrevised\n")
    assert memory_lib.parse_page(p).meta["tags"] == ["auth", "security"]


def test_a_scalar_sources_value_is_not_exploded_into_characters(store):
    """`sources: src/real.ts` parsed to a string, and set() over a string yields
    one source per character — destroying the page's only anchor to the code."""
    p = memory_write.write_page(store, "s", "t", "bug", ["src/real.ts"], "## Cause\n\n" + LONG)
    raw = p.read_text(encoding="utf-8")
    p.write_text(raw.replace("sources:\n  - src/real.ts", "sources: src/real.ts"),
                 encoding="utf-8")
    memory_write.write_page(store, "s", "t", "bug", ["src/other.ts"], "## Cause\n\nagain\n")
    assert memory_lib.parse_page(p).meta["sources"] == ["src/other.ts", "src/real.ts"]


def test_the_merge_reports_what_it_replaced(store):
    """Replacing a section is destructive in the default gitignored store, where
    no VCS sits behind the file. It must at least be visible."""
    memory_write.write_page(store, "s", "t", "concept", ["a.ts"], "## One\n\nfirst\n")
    result = memory_write.merge("## One\n\nfirst\n", "## One\n\nsecond\n\n## Two\n\nnew\n")
    assert result.replaced == ["## One"]
    assert result.appended == ["## Two"]


def test_a_nested_fence_is_still_one_fence(store):
    """Quoting a memory page requires a longer fence around a page that already
    contains one. The splitter matched exactly three backticks, so the first inner
    ``` closed the ```` fence and the quoted heading became a real one — the fix
    for fenced sections did not cover the case that motivated it."""
    # The realistic shape: one memory page quoting another memory page, which
    # itself quotes markdown. Toggling on every ```-run leaves the *second*
    # quoted `## Cause` looking like a real heading.
    original = (
        "## Cause\n\nThe renderer keeps a context across display sleep.\n\n"
        "## Format\n\nA page that documents the format looks like this:\n\n"
        "````markdown\n## Cause\n\nA page looks like this:\n\n"
        "```markdown\n## Cause\n\nwhat went wrong\n```\n````\n\n"
        "SENTINEL kept below the fence.\n\n## Fix\n\nland the fix\n")
    # The direct property: quoted headings are not headings. Matching exactly
    # three backticks parsed a phantom fourth section here.
    assert [h for h, _ in memory_write.split_sections(original) if h] == [
        "## Cause", "## Format", "## Fix"]

    memory_write.write_page(store, "s", "t", "bug", ["a.ts"], original)
    p = memory_write.write_page(store, "s", "t", "bug", ["a.ts"], "## Cause\n\nrewritten\n")
    body = body_of(p)
    assert "rewritten" in body
    assert "what went wrong" in body
    assert "SENTINEL kept below the fence." in body
    assert "land the fix" in body
    assert body.count("````") == 2


def test_a_repeated_header_in_the_incoming_body_keeps_both_copies(store):
    """Building the incoming sections as a dict dropped all but the last of two
    sections sharing a header — on a merge only, so a new page kept both and the
    next write to the same slug quietly lost one."""
    memory_write.write_page(store, "s", "t", "concept", ["a.ts"], "## Context\n\nsetup\n")
    p = memory_write.write_page(
        store, "s", "t", "concept", ["a.ts"],
        "## Finding\n\nFIRST-FINDING\n\n## Finding\n\nSECOND-FINDING\n")
    body = body_of(p)
    assert "FIRST-FINDING" in body and "SECOND-FINDING" in body


def test_a_repeated_header_already_on_the_page_is_not_duplicated(store):
    """Replacing every occurrence wrote the same incoming text into the page twice."""
    memory_write.write_page(store, "s", "t", "concept", ["a.ts"],
                            "## Note\n\nfirst\n\n## Other\n\nx\n\n## Note\n\nsecond\n")
    p = memory_write.write_page(store, "s", "t", "concept", ["a.ts"], "## Note\n\nreplaced\n")
    assert body_of(p).count("replaced") == 1


def test_a_title_ending_in_a_quote_survives_a_rewrite(store):
    """`.strip("\\"'")` ate a real character, so such a title lost one more on every
    write until it was gone."""
    title = 'The "reap loop"'
    memory_write.write_page(store, "s", title, "bug", ["a.ts"], "## Cause\n\n" + LONG)
    p = memory_write.write_page(store, "s", title, "bug", ["a.ts"], "## Cause\n\nagain\n")
    assert memory_lib.parse_page(p).title == title
