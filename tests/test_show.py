"""`lore show <slug>` prints one page, which the contract used to do with `cat`.

`cat <store>/<slug>.md` was correct and nobody could type it: the store path is
absolute and only the first line of a search result carries it. One word that
takes the slug the search printed is the same action with nothing to copy.
"""
from pagelore import instructions, show, write


def test_show_prints_the_page_the_search_named(populated, capsys):
    assert show.main(["webgl-context-loss", "--store", str(populated)]) == 0
    out = capsys.readouterr().out
    assert out == (populated / "webgl-context-loss.md").read_text(encoding="utf-8")


def test_a_slug_that_is_not_there_is_refused_with_the_search_as_the_fix(populated, capsys):
    assert show.main(["no-such-page", "--store", str(populated)]) == 2
    err = capsys.readouterr().err
    assert "no-such-page" in err
    assert "FIX: lore search" in err


def test_a_superseded_page_says_so_before_the_page(populated, capsys):
    """Search lifts the replacement above the old page; `show` asked for the old
    page by name, so it has to say the same thing on its own."""
    write.stamp_superseded(populated, "webgl-context-loss", "webgl-context-loss-v2")
    assert show.main(["webgl-context-loss", "--store", str(populated)]) == 0
    captured = capsys.readouterr()
    assert "superseded by webgl-context-loss-v2" in captured.err
    assert "## Cause" in captured.out


def test_the_block_hands_the_agent_show_rather_than_cat():
    block = instructions.render()
    assert "lore show <slug>" in block
    assert "cat <" not in block
