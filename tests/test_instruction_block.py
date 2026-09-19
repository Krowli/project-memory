"""The block an agent reads every turn, and the command it hands them.

Measured: with this block in the agent's instruction file the agent searched the
store before answering 15 times out of 15 on a task-shaped prompt; without it,
never. So the assertions here are not about formatting — each one guards a phrase
or a mechanism that measurement paid for.

The old version of this file spent seven of its eleven tests on "does this
hard-coded script path resolve in one of three documented install layouts". That
whole class is gone: `lore` is one command wherever it was installed from. Those
tests are not replaced, they are unnecessary, and that is the clearest single
argument for the repackage.
"""
import re
from pathlib import Path

import pagelore
from pagelore import instructions
from pagelore.cli import COMMANDS

REPO = Path(__file__).resolve().parents[1]


def test_the_block_carries_the_trigger_in_its_wide_form():
    """The trigger is the kind of claim being made, not a list of question
    wordings. An earlier version fired on "why…" and agents read that as
    exhaustive: asked "what do you know about this project" they answered from an
    instruction file and never searched."""
    block = instructions.render()
    assert "Before stating anything about this project" in block
    assert "what it does" in block
    assert "not a substitute" in block


def test_every_command_the_block_hands_an_agent_is_a_real_subcommand():
    """The old block named a script path that was correct in one install mode of
    three, and the first thing an agent did with it was fail on ENOENT. These have
    to be resolvable by the CLI rather than by a filesystem layout."""
    named = set(re.findall(r"^\s*lore (\w[\w-]*)", instructions.render(), re.M))
    assert named, "the block hands the agent no command at all"
    assert named <= set(COMMANDS), f"the block names {named - set(COMMANDS)}"


def test_the_repos_own_pointer_file_is_the_rendered_block():
    """Two copies of one contract drift, and the one that drifts is the one nobody
    opens. A byte comparison is the cheapest thing that prevents it."""
    assert (REPO / "AGENTS.md").read_text(encoding="utf-8") == instructions.render()


def test_renaming_the_command_leaves_the_heredoc_terminator_alone():
    """A machine where `lore` is taken installs `pagelore`, and the block is
    re-rendered with that name. The substitution is word-bounded, so `PMEOF` — the
    terminator that exists precisely so a page documenting heredocs cannot end its
    own body — survives, and so does `pagelore` itself."""
    renamed = instructions.render("pagelore")
    assert "PMEOF" in renamed
    assert re.search(r"\blore\b", renamed) is None
    assert "pagelore search" in renamed


def test_the_bare_command_says_so_when_nothing_is_connected(tmp_path, monkeypatch):
    """Measured: fifteen sessions with the block reachable searched before answering
    fifteen times, and fifteen with nothing connected searched never. Before 0.4.0 a
    copied skill directory gave a harness something to index, and fifteen sessions
    with only that — no instruction line at all — still searched, so dropping the
    packaging removed a fallback that worked. This line is the replacement: it costs
    one `is_file()` on the one surface a person reads."""
    from pagelore.cli import usage

    monkeypatch.setenv(instructions.HOME_ENV, str(tmp_path / "nothing-here"))
    assert "Run `lore init`" in usage("lore")

    monkeypatch.setenv(instructions.HOME_ENV, str(tmp_path / "connected"))
    instructions.install("lore")
    assert "Run `lore init`" not in usage("lore")


def test_the_npm_route_can_say_which_of_the_two_names_was_typed(monkeypatch):
    """A console script leaves the name in `argv[0]`; `python -m pagelore` leaves
    `__main__.py`. So the npm shim passes it in the environment, and it has to be
    honoured — otherwise someone whose machine already has a different `lore`
    installs this, runs `pagelore init`, and the block tells their agent to run
    `lore`: the other program."""
    from pagelore import cli

    monkeypatch.setenv(cli.INVOKED_AS_ENV, "pagelore")
    assert cli.invoked_as() == "pagelore"
    assert "pagelore search" in instructions.render(cli.invoked_as())

    monkeypatch.setenv(cli.INVOKED_AS_ENV, "not-one-of-ours")
    assert cli.invoked_as() in ("lore", "pagelore"), "a junk value must not reach the block"


def test_a_refresh_never_creates_the_directory_it_writes_into(tmp_path, monkeypatch):
    """Its existence is the opt-in signal. A search run in a project that never
    asked for any of this must not leave a directory in $HOME — the same rule that
    stops a read-only search from creating a store."""
    monkeypatch.setenv(instructions.HOME_ENV, str(tmp_path / "never"))
    monkeypatch.delenv(instructions.NO_REFRESH_ENV, raising=False)
    assert instructions.refresh_quietly() is False
    assert not (tmp_path / "never").exists()


def test_a_refresh_brings_a_stale_block_up_to_date(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv(instructions.HOME_ENV, str(home))
    monkeypatch.delenv(instructions.NO_REFRESH_ENV, raising=False)
    instructions.install("lore")
    (home / instructions.BLOCK).write_text("stale\n", encoding="utf-8")

    assert instructions.refresh_quietly() is True
    assert (home / instructions.BLOCK).read_text(encoding="utf-8") == instructions.render()
    # Idempotent: nothing to do the second time, and no write.
    assert instructions.refresh_quietly() is False


def test_a_refresh_keeps_the_command_name_this_machine_was_set_up_with(tmp_path, monkeypatch):
    monkeypatch.setenv(instructions.HOME_ENV, str(tmp_path))
    monkeypatch.delenv(instructions.NO_REFRESH_ENV, raising=False)
    instructions.install("pagelore")
    (tmp_path / instructions.BLOCK).write_text("stale\n", encoding="utf-8")

    instructions.refresh_quietly()
    assert "pagelore search" in (tmp_path / instructions.BLOCK).read_text(encoding="utf-8")


def test_a_pre_0_4_block_is_replaced_rather_than_duplicated():
    """Whoever upgrades from the skill-directory layout has an install.sh block in
    their config pointing at a directory that is about to be deleted. Matching only
    the new marker would leave them with two blocks, one of them dead — the exact
    duplication the fencing exists to prevent."""
    legacy = (f"# My rules\n\n{instructions.MARK_LEGACY}\n"
              f"@~/.agents/skills/project-memory/USE.md\n{instructions.MARK_LEGACY_END}\n")
    new, action = instructions.replace_block(legacy, instructions.fenced("@/new/AGENT.md"))
    assert action == "updated"
    assert "USE.md" not in new
    assert new.count(instructions.MARK_END) == 1
    assert instructions.MARK_LEGACY_END not in new, "the retired product's marker survived"
    assert new.startswith("# My rules")


def test_stripping_takes_out_the_block_and_nothing_around_it():
    text, _ = instructions.replace_block("# My rules\n\nDo not break things.\n",
                                         instructions.fenced("@/x/AGENT.md"))
    stripped, removed = instructions.strip_block(text)
    assert removed is True
    assert stripped == "# My rules\n\nDo not break things.\n"
    assert instructions.strip_block(stripped) == (stripped, False)


def test_this_repository_uses_its_own_memory():
    """A memory tool whose own repository has no memory is making an argument it
    does not believe. These pages are the fixture for every claim in the README."""
    pages = sorted((REPO / ".memory").glob("*.md"))
    assert len(pages) >= 5, f"only {len(pages)} pages"


def test_the_projects_own_store_is_tracked_on_purpose():
    """The default is a private store. This repository is the exception, and the
    marker is what stops the scripts from gitignoring it behind the author."""
    assert (REPO / ".memory" / ".tracked").is_file()
    assert ".memory/" not in (REPO / ".gitignore").read_text(encoding="utf-8")


def test_the_version_is_not_hardcoded_into_the_shipped_block():
    assert pagelore.__version__ not in instructions.packaged()
