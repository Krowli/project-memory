"""The packaging contract: manifests stay valid and versions stay in sync."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = ROOT / "skills" / "project-memory" / "SKILL.md"
PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
MARKET = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def _frontmatter():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return text.split("---\n", 2)[1]


def test_skill_md_exists_with_frontmatter():
    fm = _frontmatter()
    assert "name:" in fm and "description:" in fm


def test_skill_name_matches_directory():
    fm = _frontmatter()
    name = next(ln.split(":", 1)[1].strip()
                for ln in fm.splitlines() if ln.startswith("name:"))
    assert name == SKILL_MD.parent.name
    assert re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name), "spec: lowercase, no double hyphen"
    assert len(name) <= 64


def test_description_within_spec_limit():
    fm = _frontmatter()
    desc = next(ln.split(":", 1)[1].strip()
                for ln in fm.splitlines() if ln.startswith("description:"))
    assert 0 < len(desc) <= 1024


def test_frontmatter_uses_only_portable_spec_fields():
    """Fields outside the Agent Skills spec break claude.ai upload and packaging."""
    allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    keys = {ln.split(":", 1)[0] for ln in _frontmatter().splitlines()
            if ln and not ln.startswith((" ", "-", "#"))}
    assert keys <= allowed, f"non-portable frontmatter: {keys - allowed}"


def test_versions_are_semver_and_in_sync():
    assert SEMVER.match(PLUGIN["version"])
    entry = MARKET["plugins"][0]
    assert entry["version"] == PLUGIN["version"], "bump both manifests together"


def test_marketplace_required_fields():
    assert MARKET["name"] and MARKET["owner"]["name"] and MARKET["plugins"]
    entry = MARKET["plugins"][0]
    assert entry["name"] == PLUGIN["name"]
    assert entry["source"] == "./"


def test_declared_skill_paths_exist():
    for rel in MARKET["plugins"][0]["skills"]:
        assert (ROOT / rel).joinpath("SKILL.md").is_file(), rel


def test_changelog_mentions_current_version():
    assert PLUGIN["version"] in (ROOT / "CHANGELOG.md").read_text()
