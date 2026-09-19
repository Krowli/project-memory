"""`lore init` — connect an agent to the memory, and decide where a store lives.

Two questions, and nothing else. They are the only part of the old shell installer
that packaging does not subsume: pipx knows how to put a program on PATH and
nothing about which file an agent reads.

Both are previewed before anything is written and confirmed before anything is
changed, because the target is the user's own global configuration. The default
for the agent question is "none": writing into someone's `~/.claude/CLAUDE.md`
unasked is not a default anyone gets to choose for them.

Interactivity is a parameter, not a call to `isatty()` buried in the middle. A
test that pipes stdin into a wizard deciding by `isatty()` takes the
non-interactive branch and proves nothing about the questions — which is exactly
what happened to the shell installer, where a dead prompt shipped and passed
review.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import instructions
from .cli import add_version
from .lib import TRACKED_MARKER

# Each agent, the file it reads every turn, and whether it can include by path.
# Cursor has no file — its rules live in a text box — so it is instructions only.
AGENTS = {
    "claude": ("Claude Code", Path.home() / ".claude" / "CLAUDE.md", "include"),
    "gemini": ("Gemini CLI", Path.home() / ".gemini" / "GEMINI.md", "include"),
    "codex": ("Codex CLI", Path.home() / ".codex" / "AGENTS.md", "paste"),
}
ORDER = ("claude", "gemini", "codex")
STORE_MODES = ("gitignored", "tracked", "home")


def _project_root() -> Path | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None


def manual(cmd: str, out) -> None:
    block = instructions.block_path()
    print(f"""
To connect an agent yourself, one line, once:

  Claude Code     add to ~/.claude/CLAUDE.md
  Gemini CLI      add to ~/.gemini/GEMINI.md

      @{block}

  Codex CLI       paste that file's contents into ~/.codex/AGENTS.md
  Cursor          paste them into Customize → Rules

Per project instead of per machine: put the same line in the project's own
CLAUDE.md or AGENTS.md. Only one agent: put it in that agent's definition.

Or without questions:
  {cmd} init --agent claude --agent codex --yes
  {cmd} init --store tracked --yes""", file=out)


def _write_agents(chosen: list[str], cmd: str, out) -> None:
    block_file = instructions.block_path()
    for key in chosen:
        _, target, kind = AGENTS[key]
        body = f"@{block_file}" if kind == "include" else instructions.render(cmd).strip()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            old = target.read_text(encoding="utf-8") if target.exists() else ""
            new, action = instructions.replace_block(old, instructions.fenced(body))
            target.write_text(new, encoding="utf-8")
            print(f"{action}:   {target}", file=out)
        except OSError as exc:
            # One unwritable target must not abandon the others.
            print(f"skipped:   {target} ({exc})", file=out)


def _preview(chosen: list[str], cmd: str, out) -> None:
    block_file = instructions.block_path()
    lines = instructions.render(cmd).strip().count("\n") + 1
    print("\nThis will change:", file=out)
    for key in chosen:
        _, target, kind = AGENTS[key]
        print(f"  {target}", file=out)
        if kind == "include":
            print(f"      + @{block_file}", file=out)
        else:
            print(f"      + the contents of {block_file} ({lines} lines)", file=out)
    print("", file=out)


def _apply_store(mode: str, root: Path, out) -> None:
    store = root / ".memory"
    if mode == "gitignored":
        # Deliberately creates nothing: the first write creates the store and
        # shields it as it does. A machine-setup command that makes a directory
        # inside someone's repository is a surprise, and this one would be useless.
        print(f"store:     {store} will appear on the first write, gitignored as it is created",
              file=out)
        return
    if mode == "tracked":
        # Must act now. `.tracked` has to exist before the first write, or the
        # store gitignores itself behind a user who asked for the opposite.
        store.mkdir(parents=True, exist_ok=True)
        (store / TRACKED_MARKER).write_text(
            "These pages are committed on purpose. Do not gitignore this store.\n",
            encoding="utf-8")
        print(f"store:     {store}  (committed with the repo — do not write secrets here)",
              file=out)
        return
    # `instructions.home()`, not `Path.home() / ".project-memory"`: the same directory
    # by default, but one place decides where it is. Two computations of one path drift,
    # and this one drifted in the only way that matters — it could not be redirected, so
    # a test of this mode wrote into the real home directory on a CI machine.
    target = instructions.home() / root.name
    target.mkdir(parents=True, exist_ok=True)
    if store.exists() and not store.is_symlink():
        print(f"note:      {store} already exists as a real directory; leaving it alone.\n"
              f"           Move its contents to {target} and delete it to finish the switch.",
              file=out)
        return
    if store.is_symlink():
        store.unlink()
    store.symlink_to(target)
    _ignore(root, out)
    print(f"store:     {target}  (outside the repo, reached via .memory/ symlink)", file=out)


def _ignore(root: Path, out) -> None:
    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if any(line.strip().strip("/") == ".memory" for line in existing.splitlines()):
        return
    prefix = "" if (not existing or existing.endswith("\n")) else "\n"
    with gitignore.open("a", encoding="utf-8") as fh:
        fh.write(f"{prefix}\n# project-memory: notes stay local\n.memory/\n")
    print("ignored:   .memory/ added to .gitignore", file=out)


def main(argv: list[str] | None = None, *, prog: str = "lore init",
         stdin=None, stdout=None, interactive: bool | None = None) -> int:
    ap = argparse.ArgumentParser(prog=prog, description="Connect an agent to the memory.")
    add_version(ap)
    ap.add_argument("--agent", action="append", default=[], choices=sorted(AGENTS),
                    help="connect this agent; repeatable; implies --yes")
    ap.add_argument("--store", choices=STORE_MODES, help="where this project's pages live")
    ap.add_argument("--command", default=None,
                    help="the command name to write into the block (default: how you ran this)")
    ap.add_argument("--yes", action="store_true", help="take the answers as given, ask nothing")
    ap.add_argument("--print", dest="show", action="store_true",
                    help="print the line to add and exit")
    args = ap.parse_args(argv)

    out = stdout or sys.stdout
    inp = stdin or sys.stdin
    cmd = args.command or prog.split()[0]

    # First, always: the file the line points at has to exist before the line is
    # offered. A wrong include path is the one failure that produces no error.
    block_file = instructions.install(cmd)
    print(f"pagelore, block at {block_file}\n", file=out)

    if args.show:
        print(f"@{block_file}", file=out)
        return 0

    if interactive is None:
        interactive = bool(getattr(inp, "isatty", lambda: False)()) and not args.yes
    flags_given = bool(args.agent or args.store)

    chosen = list(dict.fromkeys(args.agent))
    if not chosen and interactive:
        print("\nWhich agents should use it? The line goes into that agent's own instruction\n"
              "file, and it applies to every project you open with that agent.\n", file=out)
        for i, key in enumerate(ORDER, 1):
            label, target, _ = AGENTS[key]
            print(f"  {i}) {label:<13} {target}", file=out)
        print("  4) none — show me what to add and I will do it myself  [default]\n", file=out)
        print("Choice (several allowed, e.g. 1 3): ", end="", file=out, flush=True)
        picks = (inp.readline() or "").split()
        chosen = [ORDER[int(p) - 1] for p in picks if p.isdigit() and 1 <= int(p) <= 3]
        if picks and not chosen:
            print(f"nothing recognised in \"{' '.join(picks)}\"", file=out)

    if chosen:
        confirmed = args.yes or flags_given
        if not confirmed and interactive:
            _preview(chosen, cmd, out)
            print("Write it? [Y/n]: ", end="", file=out, flush=True)
            answer = (inp.readline() or "").strip().lower()
            confirmed = answer in ("", "y", "yes")
            if not confirmed:
                print("nothing written", file=out)
        if confirmed:
            _write_agents(chosen, cmd, out)
            print("\nStart a new agent session for it to take effect.", file=out)
        else:
            manual(cmd, out)
    else:
        manual(cmd, out)

    root = _project_root()
    if root is not None and (args.store or interactive):
        mode = args.store
        if mode is None:
            print(f"\nWhere should this project's memory pages live?   {root}\n", file=out)
            print("  1) .memory/ here, private — appears on the first write, gitignored  [default]",
                  file=out)
            print("  2) .memory/ here, committed to git — reviewed in PRs, shared with the team",
                  file=out)
            print(f"  3) ~/.project-memory/{root.name}/ — outside the repo, via a .memory/ symlink\n",
                  file=out)
            print("Choice [1]: ", end="", file=out, flush=True)
            answer = (inp.readline() or "").strip()
            mode = {"": "gitignored", "1": "gitignored", "2": "tracked",
                    "3": "home"}.get(answer, "gitignored")
        _apply_store(mode, root, out)

    if not interactive and not flags_given:
        print("\nNo terminal to confirm on, so nothing else was changed.", file=out)

    print(f"\nTo take it all back out:  {cmd} uninstall", file=out)
    return 0
