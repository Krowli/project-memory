"""Knowing what you have, and getting what is newer.

A `curl` install has no package manager to ask. Until these existed, neither the
user nor the agent could tell 0.1.0 from 0.2.0 on disk, and the installer took the
tip of `main`, so two people running the same command on the same day could get
different code and neither could say which.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import conftest
import memory_lib
import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "project-memory" / "scripts"
INSTALL = REPO / "install.sh"


@pytest.mark.parametrize("name", ["memory_search.py", "memory_write.py", "memory_stats.py"])
def test_every_script_reports_its_version(name):
    proc = subprocess.run([sys.executable, str(SCRIPTS / name), "--version"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert memory_lib.VERSION in proc.stdout
    assert "project-memory" in proc.stdout


def test_the_runtime_version_matches_the_manifests():
    """VERSION is a ninth place the version lives. The drift test in
    test_agent_manifests covers the other eight; this ties the runtime to them."""
    declared = json.loads((REPO / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8"))["version"]
    assert memory_lib.VERSION == declared


# install.sh is a POSIX shell installer and is not a Windows entry point — there
# `bash` resolves to the WSL stub, which answers in UTF-16 and installs nothing.
# Windows users install through the plugin marketplace instead.
@conftest.needs_posix
def test_the_installer_help_shows_the_whole_header():
    """`--help` prints a fixed line range of this file's own comment block. Adding
    a line to the header silently truncated it before, hiding two store modes."""
    header = []
    for line in INSTALL.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.startswith("#"):
            break
        header.append(line)
    shown = subprocess.run(["bash", str(INSTALL), "--help"],
                           capture_output=True, text=True).stdout
    assert header, "no header comment block found"
    assert header[-1] in shown, "the last header line is not printed by --help"


@conftest.needs_posix
def test_the_installer_reports_what_is_installed_and_what_is_newer(tmp_path):
    proc = subprocess.run(["bash", str(INSTALL), "--check", "--dest", str(tmp_path)],
                          capture_output=True, text=True,
                          env={**os.environ, "HOME": str(tmp_path),
                               "PROJECT_MEMORY_REPO": str(REPO)})
    assert proc.returncode == 0, proc.stderr
    assert "installed:" in proc.stdout
    assert "latest:" in proc.stdout


def test_the_installer_prefers_a_released_tag_over_the_branch():
    """The default used to be `main`, so an install was whatever had landed that
    hour and a version number meant nothing."""
    source = INSTALL.read_text(encoding="utf-8")
    assert 'REF="${PROJECT_MEMORY_REF:-}"' in source, "REF still defaults to a branch"
    assert re.search(r"latest_tag\(\)\s*\{", source), "no tag resolution in the installer"
    assert 'REF="$(latest_tag)"' in source


@conftest.needs_posix
def test_the_installer_places_the_skill_and_touches_no_settings(tmp_path):
    """The whole integration is the skill on disk. Nothing is registered with
    any agent's settings, because a mechanism one harness has is not a
    mechanism; the scripts it installs have to run with the interpreter it
    resolved, and that is all the install has to prove."""
    home = tmp_path / "home"
    home.mkdir()
    # The branch that is checked out, so the test exercises this tree rather
    # than whatever main had.
    branch = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    proc = subprocess.run(
        ["bash", str(INSTALL), "--no-store", "--dest", str(tmp_path / "skills")],
        capture_output=True, text=True,
        env={**os.environ, "HOME": str(home), "PROJECT_MEMORY_REPO": str(REPO),
             "PROJECT_MEMORY_REF": branch if branch and branch != "HEAD" else "main"})
    assert proc.returncode == 0, proc.stderr
    assert "verified:" in proc.stdout
    assert not (home / ".claude" / "settings.json").exists()
    assert not (tmp_path / "skills" / "project-memory" / "hooks").exists()

    search = tmp_path / "skills" / "project-memory" / "scripts" / "memory_search.py"
    run = subprocess.run([sys.executable, str(search), "--store", str(tmp_path / "none"),
                          "anything"], capture_output=True, text=True, cwd=tmp_path)
    assert run.returncode == 0, run.stderr
