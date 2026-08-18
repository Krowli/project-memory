"""Every command a pointer file hands an agent has to be runnable.

`CLAUDE.md`, `AGENTS.md` and `GEMINI.md` all hard-coded
`.agents/skills/project-memory/scripts/...`, which exists in exactly one install
mode — `install.sh --project`. Not in a bare clone, which is the case CLAUDE.md
says it exists for; not after the default install, which goes to
`~/.agents/skills`. The contract of this repository was unexecutable for the
whole life of the project, and the first thing an agent does with it is fail.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
POINTERS = ["CLAUDE.md", "AGENTS.md", "GEMINI.md"]

# Where the scripts can legitimately be, by install mode.
HOME_INSTALL = "~/.agents/skills/project-memory/scripts/"
COMMAND = re.compile(r"python3 (\S*memory_(?:search|write)\.py)")


def commands(rel: str) -> list[str]:
    return COMMAND.findall((REPO / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("rel", POINTERS)
def test_the_file_names_at_least_one_command(rel):
    assert commands(rel), f"{rel} tells the agent to search but shows no command"


@pytest.mark.parametrize("rel", POINTERS)
def test_every_command_path_resolves_in_a_documented_layout(rel):
    for path in commands(rel):
        if path.startswith(HOME_INSTALL):
            continue
        assert (REPO / path).is_file(), (
            f"{rel} runs {path}, which is neither a path in this repository nor "
            f"the default install location {HOME_INSTALL}")


@pytest.mark.parametrize("rel", POINTERS)
def test_the_file_names_the_other_install_layouts(rel):
    """One hard-coded path cannot be right for every install mode, so the file has
    to say which layouts exist rather than pretend there is only one."""
    text = (REPO / rel).read_text(encoding="utf-8")
    assert ".agents/skills/project-memory" in text
    assert "skills/project-memory/scripts" in text


def test_claude_md_leads_with_the_clone_layout():
    """It states that it exists for the case where the repo is cloned rather than
    installed, so its first command has to be the one that works in a clone."""
    assert commands("CLAUDE.md")[0] == "skills/project-memory/scripts/memory_search.py"


def test_skill_md_says_what_its_relative_paths_are_relative_to():
    text = (REPO / "skills" / "project-memory" / "SKILL.md").read_text(encoding="utf-8")
    assert "relative to this skill" in text


def test_this_repository_uses_its_own_memory():
    """A memory tool whose own repository has no memory is making an argument it
    does not believe. These pages are the fixture for every claim in the README."""
    store = REPO / ".memory"
    pages = sorted(store.glob("*.md"))
    assert len(pages) >= 5, f"only {len(pages)} pages in {store}"


def test_the_projects_own_store_is_tracked_on_purpose():
    """The default is a private store. This repository is the exception, and the
    marker is what stops the scripts from gitignoring it behind the author."""
    assert (REPO / ".memory" / ".tracked").is_file()
    assert ".memory/" not in (REPO / ".gitignore").read_text(encoding="utf-8")
