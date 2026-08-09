"""Every agent gets its own manifest file, so the same facts are written six
times. These tests pin the ones that will drift: the version, the skills path,
and the repository URL."""
import json
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
    versions = {rel: load(rel)["version"] for rel in VERSIONED}
    versions[".claude-plugin/marketplace.json"] = load(
        ".claude-plugin/marketplace.json")["plugins"][0]["version"]
    assert len(set(versions.values())) == 1, f"version drift across manifests: {versions}"


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

def test_skill_ships_a_gitignore_for_its_own_bytecode():
    """Running the scripts leaves .pyc files next to them. Installed into someone
    else's repo, those show up in their very first `git status`."""
    ignore = REPO / "skills" / "project-memory" / ".gitignore"
    assert ignore.is_file()
    assert "__pycache__" in ignore.read_text()
