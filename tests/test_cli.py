"""The router: which words are commands, and what the bare command lists.

The first person to look for the version could not find it. `--version` existed
and worked, and nothing on the one screen a person reads said so.
"""
import re

from pagelore import cli


def test_version_is_a_command_as_well_as_a_flag(capsys):
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.strip() == cli.version_line("lore")


def test_the_command_list_names_every_command_and_the_version(monkeypatch, tmp_path):
    from pagelore import instructions
    monkeypatch.setenv(instructions.HOME_ENV, str(tmp_path))
    listed = set(re.findall(r"^\s*lore (\w+)", cli.usage("lore"), re.M))
    assert set(cli.COMMANDS) <= listed, f"not listed: {set(cli.COMMANDS) - listed}"
    assert "version" in listed
