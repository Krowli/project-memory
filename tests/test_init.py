"""`lore init` asks two questions, and the questions have to be tested.

The shell installer this replaces shipped a dead prompt: a question placed after
the value it was supposed to decide, so both answers led to the same place. It
passed review because the only test that could reach the prompts drove a pty, and
nobody wrote one for that branch.

So interactivity here is a parameter with `isatty()` as its default, and these
drive the interactive path directly. A test that merely pipes stdin would take the
non-interactive branch and prove exactly as little as piping into the old script
did. One pty test at the end proves the default wiring itself.
"""
import io
import os
import subprocess
import sys
from pathlib import Path

import conftest
import pytest

from pagelore import doctor, init, instructions, uninstall, write

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def machine(tmp_path, monkeypatch):
    """A throwaway home with a git repo under foot, so both questions are live."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "CLAUDE.md").write_text("# My rules\n\nDo not break things.\n",
                                                encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv(instructions.HOME_ENV, str(home / ".project-memory"))
    monkeypatch.setenv(instructions.NO_REFRESH_ENV, "1")
    monkeypatch.chdir(project)
    # AGENTS maps agent name to an absolute path resolved at import time, so it has
    # to be rebound for a fake home.
    monkeypatch.setitem(init.AGENTS, "claude",
                        ("Claude Code", home / ".claude" / "CLAUDE.md", "include"))
    monkeypatch.setitem(init.AGENTS, "gemini",
                        ("Gemini CLI", home / ".gemini" / "GEMINI.md", "include"))
    monkeypatch.setitem(init.AGENTS, "codex",
                        ("Codex CLI", home / ".codex" / "AGENTS.md", "paste"))
    return home, project


def run(answers: str, argv=None, interactive=True):
    out = io.StringIO()
    code = init.main(argv or [], stdin=io.StringIO(answers), stdout=out,
                     interactive=interactive)
    return code, out.getvalue()


def test_the_block_is_written_before_the_line_that_points_at_it(machine):
    """Order, not taste: an `@path` to a missing file produces no error in any
    harness. The agent silently loads nothing, which is the failure this whole
    design exists to avoid."""
    code, out = run("4\n")
    assert code == 0
    assert instructions.block_path().is_file()
    assert str(instructions.block_path()) in out


def test_choosing_an_agent_shows_the_exact_change_and_asks_first(machine):
    home, _ = machine
    _, out = run("1\ny\n1\n")
    assert "This will change:" in out
    assert str(home / ".claude" / "CLAUDE.md") in out
    assert f"@{instructions.block_path()}" in out

    written = (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert written.startswith("# My rules\n\nDo not break things.\n"), "it ate the user's text"
    assert f"@{instructions.block_path()}" in written
    assert instructions.MARK_BEGIN in written


def test_declining_the_preview_writes_nothing_and_still_says_what_to_add(machine):
    home, _ = machine
    _, out = run("1\nn\n1\n")
    assert "nothing written" in out
    assert "To connect an agent yourself" in out
    assert instructions.MARK_BEGIN not in (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")


def test_the_default_answer_connects_nothing(machine):
    """Writing into someone's global agent configuration unasked is not a default
    anyone gets to choose for them."""
    home, _ = machine
    _, out = run("\n\n")
    assert instructions.MARK_BEGIN not in (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "To connect an agent yourself" in out


def test_running_it_twice_replaces_the_block_rather_than_stacking_one(machine):
    home, _ = machine
    run("1\ny\n1\n")
    run("1\ny\n1\n")
    written = (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert written.count(instructions.MARK_BEGIN) == 1
    assert written.count(instructions.MARK_END) == 1


def test_codex_gets_the_text_because_it_cannot_include_a_file(machine):
    home, _ = machine
    run("3\ny\n1\n")
    written = (home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
    assert "Before stating anything about this project" in written
    assert f"@{instructions.block_path()}" not in written


def test_the_private_store_creates_nothing(machine):
    """`ensure_store` already creates and shields the store at the first write, so
    a directory made here would be both redundant and a surprise inside someone's
    repository."""
    _, project = machine
    run("4\n1\n")
    assert not (project / ".memory").exists()


def test_the_tracked_store_is_marked_before_the_first_write(machine):
    """`.tracked` has to exist before anything writes, or the store gitignores
    itself behind a user who asked for the opposite."""
    _, project = machine
    run("4\n2\n")
    assert (project / ".memory" / ".tracked").is_file()
    gitignore = project / ".gitignore"
    if gitignore.exists():
        assert ".memory/" not in gitignore.read_text(encoding="utf-8")


def test_the_home_store_symlinks_out_of_the_repo_and_gitignores_the_link(machine):
    """The third store mode, and the one nothing covered. `lib.py` and `index.py`
    both carry comments about what it invites — a network filesystem, a dead symlink
    — so the mode they describe has to exist and work."""
    home, project = machine
    code, out = run("", argv=["--store", "home", "--yes"], interactive=False)
    assert code == 0

    link = project / ".memory"
    assert link.is_symlink(), "the store is a real directory, not a link out of the repo"
    target = link.resolve()
    assert home in target.parents, f"{target} is not under the fake home"
    assert ".memory/" in (project / ".gitignore").read_text(encoding="utf-8")
    assert str(target) in out

    # The link has to be writable end to end, or the mode is decorative.
    (project / "src").mkdir()
    (project / "src" / "a.ts").write_text("export {}\n", encoding="utf-8")
    body = ("## Cause\n\n" + "Enough body to clear the two-hundred-character floor that the "
            "write gate applies, so that the page actually lands in the symlinked store "
            "rather than being refused long before it ever gets that far at all.\n")
    assert write.main(["--slug", "probe", "--title", "Probe", "--kind", "bug",
                       "--source", "src/a.ts", "--body", body]) == 0
    assert (target / "probe.md").is_file()


def test_no_terminal_asks_nothing_stalls_never_and_still_writes_the_block(machine):
    home, project = machine
    code, out = run("", interactive=False)
    assert code == 0
    assert instructions.block_path().is_file()
    assert "No terminal to confirm on" in out
    assert instructions.MARK_BEGIN not in (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert not (project / ".memory").exists()


def test_flags_are_the_confirmation_so_it_works_in_a_pipeline(machine):
    home, project = machine
    code, _ = run("", argv=["--agent", "claude", "--store", "tracked", "--yes"],
                  interactive=False)
    assert code == 0
    assert instructions.MARK_BEGIN in (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert (project / ".memory" / ".tracked").is_file()


def test_uninstall_takes_out_the_block_and_leaves_the_pages(machine, capsys):
    home, project = machine
    run("1\ny\n2\n")
    (project / ".memory" / "a-page.md").write_text("---\nslug: a-page\n---\n\nkeep me\n",
                                                   encoding="utf-8")

    assert uninstall.main([]) == 0
    assert (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8") == \
        "# My rules\n\nDo not break things.\n"
    assert (project / ".memory" / "a-page.md").read_text(encoding="utf-8") == \
        "---\nslug: a-page\n---\n\nkeep me\n"
    assert ".memory/" in capsys.readouterr().out


def test_doctor_calls_nothing_connected_a_fault(machine):
    """Measured, an agent with the block searches 15 of 15 times and one without it
    never does. "Installed but not connected" is therefore broken, not neutral."""
    before = {row["check"]: row for row in doctor.findings()}
    assert before["connected"]["ok"] is False
    assert "nothing tells any agent" in before["connected"]["detail"]

    run("1\ny\n1\n")
    after = {row["check"]: row for row in doctor.findings()}
    assert after["connected"]["ok"] is True
    assert after["agent:claude"]["ok"] is True


def test_doctor_catches_an_include_pointing_at_a_file_that_is_gone(machine):
    """The silent failure: no harness errors on a missing `@path`, the agent just
    stops searching, and nobody connects that to whatever deleted the file."""
    run("1\ny\n1\n")
    instructions.block_path().unlink()

    claude = {row["check"]: row for row in doctor.findings()}["agent:claude"]
    assert claude["ok"] is False
    assert "MISSING" in claude["detail"]


@conftest.needs_posix
def test_it_asks_on_a_real_terminal(tmp_path):
    """Every test above drives the questions in process. This one proves the wiring
    they bypass: that on a terminal the default really does take the branch that
    asks."""
    import pty

    home = tmp_path / "home"
    home.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)

    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(project)
        os.environ.update({"HOME": str(home), "PYTHONPATH": str(REPO / "src"),
                           instructions.HOME_ENV: str(home / ".project-memory"),
                           instructions.NO_REFRESH_ENV: "1"})
        os.execv(sys.executable, [sys.executable, "-m", "pagelore", "init"])

    seen = b""
    try:
        while b"Choice" not in seen:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            seen += chunk
        os.write(fd, b"4\n1\n")
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            seen += chunk
    except OSError:
        pass
    finally:
        os.close(fd)
        os.waitpid(pid, 0)

    assert b"Which agents should use it?" in seen
