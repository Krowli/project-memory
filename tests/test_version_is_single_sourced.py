"""The version lives in one file. Everything else derives it or is checked here.

It used to live in ten hand-edited places — five plugin manifests, a marketplace
entry, `pyproject.toml`, `SKILL.md`, a runtime constant and a stamp inside the
instruction block — guarded by five separate drift tests. Those tests were not the
problem; they were the symptom. Ten places that must agree will disagree, and the
fix was to stop having ten.

What is left: one literal in `__init__.py`, one heading in the changelog, the npm
manifest (npm will not read a Python file) and the git tag. This file is what keeps
that list from growing.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import pagelore

REPO = Path(__file__).resolve().parents[1]
TRUTH = REPO / "src" / "pagelore" / "__init__.py"


def test_the_truth_is_one_literal_in_one_file():
    """A bare literal, because the build backend AST-reads it rather than importing
    it. Anything computed here breaks the build with no import to blame."""
    found = re.findall(r'^__version__ = "([^"]+)"$', TRUTH.read_text(encoding="utf-8"), re.M)
    assert found == [pagelore.__version__]


def test_pyproject_carries_no_version_of_its_own():
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in text
    assert not re.search(r"^version = ", text, re.M), "pyproject declares a second version"
    assert 'path = "src/pagelore/__init__.py"' in text


def test_the_installed_metadata_agrees():
    """Catches what reading the source cannot: an editable install whose metadata
    went stale, or a wheel built from a different tree than the one under test."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        installed = version("pagelore")
    except PackageNotFoundError:
        pytest.skip("not installed; `pip install -e .` to cover this")
    assert installed == pagelore.__version__


def test_the_instruction_block_is_stamped_at_render_not_in_the_file():
    """The shipped block holds a placeholder. A literal there would be an eleventh
    place, and the one nobody would remember — it is data, not code."""
    from pagelore import instructions
    assert "{version}" in instructions.packaged()
    assert f"pagelore {pagelore.__version__}" in instructions.render()


def test_the_npm_manifest_agrees():
    """npm cannot read `__init__.py`, so this one number is copied rather than
    derived — the only copy left. `npm/scripts/vendor.js` refuses to pack when the
    two disagree, so a mismatch cannot reach a published tarball; this fails first,
    with a clearer message, and without needing Node."""
    manifest = REPO / "npm" / "package.json"
    if not manifest.exists():
        pytest.skip("npm/package.json is not in this distribution")
    declared = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    assert declared == pagelore.__version__, \
        f"npm says {declared}; set it to {pagelore.__version__}"


def test_the_changelog_has_a_section_for_it():
    """Pinned as a heading, not a substring: the release workflow's awk extracts
    exactly this shape to make the release notes."""
    changelog = REPO / "CHANGELOG.md"
    if not changelog.exists():
        pytest.skip("CHANGELOG.md is not in this distribution")
    assert re.search(rf"^## \[{re.escape(pagelore.__version__)}\]",
                     changelog.read_text(encoding="utf-8"), re.M)


def test_the_command_reports_it_and_says_which_install_answered():
    """Two install routes each put a `lore` on PATH. A user with both gets whichever
    the path order picks, and this line is their only clue which one just ran."""
    out = subprocess.run([sys.executable, "-m", "pagelore", "--version"],
                         capture_output=True, text=True,
                         env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr
    assert pagelore.__version__ in out.stdout
    assert str(Path(pagelore.__file__).resolve().parent) in out.stdout


def test_the_python_floor_is_declared_and_enforced_in_one_shape():
    """A floor that drifts either refuses an interpreter the code runs on — which is
    what kept this off a stock macOS for months — or accepts one it does not. The
    floor is read from the one normative declaration; everything else is checked
    against it, including that CI actually runs a row on it."""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^requires-python = ">=(\d+)\.(\d+)"', pyproject, re.M)
    assert m, "pyproject declares no requires-python"
    major, minor = m.group(1), m.group(2)
    floor = f"{major}.{minor}"

    assert f'target-version = "py{major}{minor}"' in pyproject, "ruff lints for another version"

    # The npm route has no metadata to refuse an old interpreter, so the package does.
    main = (REPO / "src" / "pagelore" / "__main__.py").read_text(encoding="utf-8")
    assert f"sys.version_info < ({major}, {minor})" in main

    # The npm route has no `requires-python` either, and the shim is what prints
    # the floor to a user who has no Python at all.
    shim = REPO / "npm" / "bin" / "lore.js"
    if shim.exists():
        text = shim.read_text(encoding="utf-8")
        assert f'const FLOOR = "{floor}"' in text, "the npm shim names another floor"
        assert "const TOO_OLD = 69" in text, "the shim and __main__.py must agree on 69"
        assert "raise SystemExit(69)" in main, "__main__.py must exit 69 for the shim"

    ci = REPO / ".github" / "workflows" / "test.yml"
    if ci.exists():
        assert f'python: "{floor}"' in ci.read_text(encoding="utf-8"), \
            "the floor is declared but no CI row runs it"
