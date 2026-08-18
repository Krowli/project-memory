"""Every agent gets its own manifest file, so the same facts are written six
times. These tests pin the ones that will drift: the version, the skills path,
and the repository URL."""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Manifests that carry a version string. `.claude-plugin/marketplace.json` keeps
# its version inside plugins[0], so it is checked separately below.
VERSIONED = [
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".kimi-plugin/plugin.json",
    "gemini-extension.json",
]

# Manifests whose agent loads skills from a directory path.
SKILLS_PATH = [
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".kimi-plugin/plugin.json",
]

ALL_MANIFESTS = VERSIONED + SKILLS_PATH + [
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
]


def load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("rel", sorted(set(ALL_MANIFESTS)))
def test_manifest_is_valid_json_and_names_the_plugin(rel):
    data = load(rel)
    assert data["name"] == "project-memory"


def test_all_manifests_declare_the_same_version():
    """Eight files carry this string. README's Contributing section used to name
    two of them, so the other six drifted silently until this test caught them."""
    versions = {rel: load(rel)["version"] for rel in VERSIONED}
    versions[".claude-plugin/marketplace.json"] = load(
        ".claude-plugin/marketplace.json")["plugins"][0]["version"]

    pyproject = re.search(r'^version = "([^"]+)"',
                          (REPO / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert pyproject, "pyproject.toml declares no version"
    versions["pyproject.toml"] = pyproject.group(1)

    skill = re.search(r'^  version: "([^"]+)"',
                      (REPO / "skills" / "project-memory" / "SKILL.md")
                      .read_text(encoding="utf-8"), re.M)
    assert skill, "SKILL.md metadata declares no version"
    versions["SKILL.md"] = skill.group(1)

    assert len(set(versions.values())) == 1, f"version drift across manifests: {versions}"


def test_readme_names_every_file_that_carries_the_version():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for rel in [*VERSIONED, ".claude-plugin/marketplace.json", "pyproject.toml"]:
        assert rel in readme, f"Contributing does not tell a contributor to bump {rel}"


@pytest.mark.parametrize("rel", SKILLS_PATH)
def test_skills_path_points_at_the_real_directory(rel):
    path = load(rel)["skills"]
    assert path == "./skills/"
    assert (REPO / "skills" / "project-memory" / "SKILL.md").is_file()


@pytest.mark.parametrize("rel", sorted(set(VERSIONED) - {"gemini-extension.json"}))
def test_homepage_points_at_this_repository(rel):
    assert load(rel)["homepage"] == "https://github.com/Krowli/project-memory"


def test_gemini_context_file_exists():
    """gemini-extension.json names a context file; a missing one loads nothing."""
    name = load("gemini-extension.json")["contextFileName"]
    assert (REPO / name).is_file(), f"{name} is declared but not in the repo"

@pytest.mark.parametrize("rel", ["AGENTS.md", "CLAUDE.md", "GEMINI.md"])
def test_context_files_carry_the_broad_search_trigger(rel):
    """Three files say the same thing to three different agents, so they drift
    apart one edit at a time. Each has to carry the trigger in its wide form —
    search before any claim about the project — and the warning that the file
    you are reading is not itself a substitute for the search."""
    text = (REPO / rel).read_text(encoding="utf-8")
    assert "Before stating anything about this project" in text
    assert "not a substitute" in text


def test_skill_ships_a_gitignore_for_its_own_bytecode():
    """Running the scripts leaves .pyc files next to them. Installed into someone
    else's repo, those show up in their very first `git status`."""
    ignore = REPO / "skills" / "project-memory" / ".gitignore"
    assert ignore.is_file()
    assert "__pycache__" in ignore.read_text()
