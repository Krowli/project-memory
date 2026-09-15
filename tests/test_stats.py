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


@pytest.fixture()
def sessions(tmp_path):
    """What the Stop hook leaves behind: one line per turn, the last one per
    session being the state the session ended in."""
    store = tmp_path / ".memory"
    store.mkdir()
    for event in [
        {"event": "write", "slug": "a", "mode": "create", "chars": 400, "session": "s1"},
        {"event": "stop", "session": "s1", "changed": 5, "writes": 0, "notable": True,
         "nudged": True},
        {"event": "stop", "session": "s1", "changed": 6, "writes": 1, "notable": True,
         "nudged": False},
        {"event": "stop", "session": "s2", "changed": 4, "writes": 0, "notable": True,
         "nudged": True},
        {"event": "stop", "session": "s3", "changed": 1, "writes": 0, "notable": False,
         "nudged": False},
    ]:
        memory_lib.log_event(store, event.pop("event"), **event)
    return store


def test_sessions_that_changed_things_and_recorded_nothing_are_counted(sessions):
    """The one number the Stop hook is there to move. Judged on how the session
    ended, not on any turn in the middle: s1 was nudged and then wrote."""
    s = memory_stats.summarise(memory_stats.read_log(sessions, None))
    assert s["sessions"] == 3
    assert s["sessions_unrecorded"] == 1
    assert s["nudges"] == 2
    assert s["writes_per_session"] == round(1 / 3, 3)


def test_sessions_are_printed(sessions, capsys):
    memory_stats.main(["--store", str(sessions)])
    out = capsys.readouterr().out
    assert "sessions" in out and "recorded nothing" in out
