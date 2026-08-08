import memory_search


def test_finds_page_by_body_term(populated):
    hits = memory_search.search("display sleep", populated)
    assert next(p.slug for _, p in hits) == "webgl-context-loss"


def test_title_terms_outrank_body_mentions(populated):
    hits = memory_search.search("command palette", populated)
    assert hits[0][1].slug == "command-palette-highlight"


def test_matches_cyrillic(populated):
    hits = memory_search.search("решение база", populated)
    assert any(p.slug == "sqlite-writer-ownership" for _, p in hits)


def test_no_match_returns_empty(populated):
    assert memory_search.search("kubernetes helm chart", populated) == []


def test_empty_query_returns_empty(populated):
    assert memory_search.search("   ", populated) == []


def test_respects_k(populated):
    assert len(memory_search.search("the", populated, k=1)) <= 1


def test_missing_store_does_not_raise(tmp_path):
    assert memory_search.search("anything", tmp_path / "nope") == []


def test_cli_json_output(populated, capsys):
    rc = memory_search.main(["display", "sleep", "--store", str(populated), "--json"])
    assert rc == 0
    assert "webgl-context-loss" in capsys.readouterr().out
