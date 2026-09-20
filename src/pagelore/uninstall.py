"""`lore uninstall` — take the connection back out.

`pipx uninstall` removes the program and cannot run it, so it knows nothing about
the file this program edited in the user's agent configuration. Without this
command the fenced block survives as an `@include` pointing at a file nothing will
recreate — a dangling include, which produces no error and silently stops the
agent searching. That is the same failure the whole instruction-block design was
chosen to avoid, so leaving it to `pipx` is not an option.

It removes exactly what `lore init` wrote, and says what it deliberately did not:
the pages are the user's, and a program that can delete them by accident is worse
than no uninstaller.

The MCP route is taken out the way it went in: our entry is dropped from the JSON
files this program merged it into — and a `.mcp.json` that is empty afterwards is
deleted, because this program created it, while Gemini's settings.json is never
deleted, because it did not — and where the entry went through the harness's own
`mcp add`, its `mcp remove` is run when the harness is here and printed when not.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from . import init, instructions
from .cli import add_version
from .init import AGENTS, MCP_SERVER


def _remove_mcp(root: Path | None, out) -> bool:
    """Take the MCP registration back out of every place `lore init` can put it.
    Returns True when anything was removed or a removal command was run or printed."""
    home = Path.home()
    did = False
    # The JSON files this program merges into. `.mcp.json` is ours to delete once it
    # is empty — nothing else writes it here — and settings.json never is.
    json_files = ([root / ".mcp.json", root / ".gemini" / "settings.json"] if root else []) \
        + [home / ".gemini" / "settings.json"]
    for path in json_files:
        if not path.is_file():
            continue
        try:
            changed, empty = init.remove_json_server(path)
        except OSError as exc:
            print(f"skipped:   {path} ({exc})", file=sys.stderr)
            continue
        if not changed:
            continue
        did = True
        if empty and path.name == ".mcp.json":
            path.unlink()
            print(f"removed:   {path}  (only our MCP server was in it)", file=out)
        else:
            print(f"removed:   the MCP server from {path}", file=out)
    # The files that went through the harness's own command go out the same way.
    if init.registered_in_json(init._read_json(home / ".claude.json") or {}) is not None:
        init._run_or_print(["claude", "mcp", "remove", "--scope", "user", MCP_SERVER], out)
        did = True
    codex_home = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    if init.codex_registered(codex_home / "config.toml") is not None:
        init._run_or_print(["codex", "mcp", "remove", MCP_SERVER], out)
        did = True
    return did


def main(argv: list[str] | None = None, *, prog: str = "lore uninstall") -> int:
    ap = argparse.ArgumentParser(prog=prog, description="Disconnect the memory from your agents.")
    add_version(ap)
    ap.add_argument("--yes", action="store_true",
                    help="also remove ~/.project-memory/ (the block, not your pages)")
    args = ap.parse_args(argv)

    removed = False
    for _, target, _ in AGENTS.values():
        if not target.is_file():
            continue
        try:
            old = target.read_text(encoding="utf-8")
            new, changed = instructions.strip_block(old)
            if changed:
                target.write_text(new, encoding="utf-8")
                print(f"removed:   the block in {target}")
                removed = True
        except OSError as exc:
            print(f"skipped:   {target} ({exc})", file=sys.stderr)

    removed = _remove_mcp(init._project_root(), sys.stdout) or removed

    home = instructions.home()
    if args.yes and home.is_dir():
        shutil.rmtree(home, ignore_errors=True)
        print(f"removed:   {home}")
        removed = True
    elif home.is_dir():
        print(f"kept:      {home}  (pass --yes to remove it too)")

    if not removed:
        print("nothing to remove: no block in any agent's instruction file, no MCP server "
              "registered")

    print("""
Left alone on purpose:
  .memory/ in your projects   your pages — delete a store yourself if you mean to
  anything you wrote yourself   a line you added by hand, or an agent definition

The program itself:  pipx uninstall pagelore   (or: npm uninstall -g pagelore)""")
    return 0
