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


def test_the_python_floor_is_declared_the_same_everywhere():
    """Four files state the minimum interpreter, and one of them enforces it. A
    floor that drifts either refuses an interpreter the code runs on — which is
    what kept the skill off a stock macOS — or accepts one it does not."""
    floor = "3.9"
    minor = floor.split(".")[1]
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert f'requires-python = ">={floor}"' in pyproject
    assert f'target-version = "py3{minor}"' in pyproject
    skill = (REPO / "skills" / "project-memory" / "SKILL.md").read_text(encoding="utf-8")
    assert f"Python {floor}+" in skill
    installer = INSTALL.read_text(encoding="utf-8")
    assert f"sys.version_info >= (3, {minor})" in installer
    assert f"no Python {floor}+ found" in installer


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


@conftest.needs_posix
def test_uninstall_removes_the_skill_and_the_symlink_and_nothing_else(tmp_path):
    """A program that installs itself has to be able to take itself off. The
    first version of this repository had no uninstaller at all, so the only
    instruction anyone could be given was a pair of `rm -rf` typed by hand —
    next to a directory of the user's own pages."""
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    dest = tmp_path / "skills"
    branch = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    env = {**os.environ, "HOME": str(home), "PROJECT_MEMORY_REPO": str(REPO),
           "PROJECT_MEMORY_REF": branch if branch and branch != "HEAD" else "main"}

    installed = subprocess.run(["bash", str(INSTALL), "--no-store", "--dest", str(dest)],
                               capture_output=True, text=True, env=env)
    assert installed.returncode == 0, installed.stderr
    skill = dest / "project-memory"
    link = home / ".claude" / "skills" / "project-memory"
    assert skill.is_dir() and link.is_symlink()

    # A store, and a link of someone else's pointing elsewhere: neither is ours.
    store = tmp_path / "project" / ".memory"
    store.mkdir(parents=True)
    (store / "a-page.md").write_text("---\nslug: a-page\n---\n\nkeep me\n", encoding="utf-8")
    other = home / ".claude" / "skills" / "someone-elses"
    other.symlink_to(tmp_path)

    out = subprocess.run(["bash", str(INSTALL), "--uninstall", "--dest", str(dest)],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert not skill.exists(), "the skill directory survived"
    assert not link.exists(), "the symlink survived"
    assert (store / "a-page.md").read_text(encoding="utf-8") == \
        "---\nslug: a-page\n---\n\nkeep me\n", "uninstall touched a store"
    assert other.is_symlink(), "uninstall removed a link it did not create"
    assert ".memory/" in out.stdout, "uninstall does not say what it left behind"


@conftest.needs_posix
def test_uninstall_says_so_when_there_is_nothing_to_remove(tmp_path):
    out = subprocess.run(["bash", str(INSTALL), "--uninstall", "--dest", str(tmp_path / "nope")],
                         capture_output=True, text=True,
                         env={**os.environ, "HOME": str(tmp_path)})
    assert out.returncode == 0, out.stderr
    assert "nothing to remove" in out.stdout


def test_the_readme_documents_how_to_remove_it():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "--uninstall" in readme


@conftest.needs_posix
def test_the_install_ends_by_naming_the_line_that_makes_it_work(tmp_path):
    """The scripts on disk are half the install; the agent only reaches for them
    once the instruction block is in its configuration. The installer used to end
    without mentioning that at all, so a user who ran one command was finished
    and had no way to know they were not."""
    home = tmp_path / "home"
    home.mkdir()
    branch = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    dest = tmp_path / "skills"
    out = subprocess.run(
        ["bash", str(INSTALL), "--no-store", "--dest", str(dest)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        env={**os.environ, "HOME": str(home), "PROJECT_MEMORY_REPO": str(REPO),
             "PROJECT_MEMORY_REF": branch if branch and branch != "HEAD" else "main"})
    assert out.returncode == 0, out.stderr

    named = dest / "project-memory" / "USE.md"
    assert f"@{named}" in out.stdout, "the install does not print the line to add"
    assert named.is_file(), "the install names a file it did not place"
    assert "--uninstall" in out.stdout, "the install does not say how to undo itself"


@conftest.needs_posix
def test_the_scope_question_is_skipped_when_there_is_no_terminal(tmp_path):
    """`curl … | bash` in CI, a container or a pipeline has nobody to answer. It
    takes the global install rather than stalling on a prompt no one will see."""
    home = tmp_path / "home"
    home.mkdir()
    dest = tmp_path / "skills"
    branch = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    out = subprocess.run(
        ["bash", str(INSTALL), "--no-store", "--dest", str(dest)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=str(REPO),
        env={**os.environ, "HOME": str(home), "PROJECT_MEMORY_REPO": str(REPO),
             "PROJECT_MEMORY_REF": branch if branch and branch != "HEAD" else "main"})
    assert out.returncode == 0, out.stderr
    assert "Choice [1]" not in out.stdout
    assert (dest / "project-memory").is_dir()
