"""memory_stats reads the log back. Without it the log is write-only, which is
the same failure the write gate exists to avoid."""
import json

import memory_lib
import memory_stats
import pytest


@pytest.fixture()
def logged(tmp_path):
    store = tmp_path / ".memory"
    store.mkdir()
    for event in [
        {"event": "write", "slug": "a", "mode": "create", "chars": 400},
        {"event": "write", "slug": "a", "mode": "merge", "chars": 600},
        {"event": "reject", "code": "no_sources", "slug": "b"},
        {"event": "reject", "code": "no_sources", "slug": "c"},
        {"event": "reject", "code": "body_too_short", "slug": "d"},
        {"event": "search", "query": "pty hangs", "hits": 3, "top": "a"},
        {"event": "search", "query": "kubernetes", "hits": 0, "top": None},
    ]:
        memory_lib.log_event(store, event.pop("event"), **event)
    return store


def test_counts_writes_refusals_and_searches(logged):
    s = memory_stats.summarise(memory_stats.read_log(logged, None))
    assert (s["writes"], s["creates"], s["merges"]) == (2, 1, 1)
    assert s["rejects"] == 3
    assert s["searches"] == 2


def test_reject_rate_is_a_share_of_attempts_not_of_everything(logged):
    """3 refusals against 5 write attempts — searches must not dilute it."""
    s = memory_stats.summarise(memory_stats.read_log(logged, None))
    assert s["reject_rate"] == 0.6


def test_groups_refusals_by_code(logged):
    s = memory_stats.summarise(memory_stats.read_log(logged, None))
    assert s["reject_codes"] == {"no_sources": 2, "body_too_short": 1}


def test_surfaces_the_queries_that_found_nothing(logged):
    s = memory_stats.summarise(memory_stats.read_log(logged, None))
    assert s["zero_hit_searches"] == 1
    assert s["zero_hit_queries"] == ["kubernetes"]


def test_since_filters_by_date(logged):
    assert memory_stats.read_log(logged, "2099-01-01") == []
    assert memory_stats.read_log(logged, "2000-01-01") != []


def test_a_torn_line_does_not_hide_the_rest(logged):
    """A crash mid-append leaves half a line; the log must still be readable."""
    with (logged / memory_lib.LOG_NAME).open("a", encoding="utf-8") as fh:
        fh.write('{"event": "write", "slug": "trunc')
    records = memory_stats.read_log(logged, None)
    assert len(records) == 7


def test_empty_store_reports_instead_of_crashing(tmp_path, capsys):
    rc = memory_stats.main(["--store", str(tmp_path / "nope")])
    assert rc == 0
    assert "no log entries" in capsys.readouterr().err


def test_json_output_is_machine_readable(logged, capsys):
    memory_stats.main(["--store", str(logged), "--json"])
    assert json.loads(capsys.readouterr().out)["rejects"] == 3
