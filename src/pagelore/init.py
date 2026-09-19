"""`lore init` — connect an agent to the memory, and decide where a store lives.

Three questions, and nothing else. They are the only part of the old shell installer
that packaging does not subsume: pipx knows how to put a program on PATH and
nothing about which file an agent reads.

The first question is scope, and it exists because it was missing. The wizard used
to offer three files and all three were global; the screen said "applies to every
project" and gave no alternative, which is a notice rather than a choice. The first
person to run it wanted the line in one project's own `CLAUDE.md` and had no way to
say so.

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

from . import instructions, menu
from .cli import add_version
from .lib import TRACKED_MARKER

# Each agent, the file it reads every turn, and whether it can include by path.
# Cursor has no file — its rules live in a text box — so it is instructions only.
AGENTS = {
    "claude": ("Claude Code", Path.home() / ".claude" / "CLAUDE.md", "include"),
    "gemini": ("Gemini CLI", Path.home() / ".gemini" / "GEMINI.md", "include"),
    "codex": ("Codex CLI", Path.home() / ".codex" / "AGENTS.md", "paste"),
}
# The same three agents, per project. A project file is read only inside that
# repository, so this is the answer for someone who wants the memory in one place
# and not on every project they open for the rest of the year.
PROJECT_FILES = {"claude": "CLAUDE.md", "gemini": "GEMINI.md", "codex": "AGENTS.md"}
ORDER = ("claude", "gemini", "codex")
STORE_MODES = ("gitignored", "tracked", "home")
SCOPES = ("global", "project")


def target_for(key: str, root: Path | None) -> tuple[str, Path, str]:
    """The label, file and mechanism for one agent at the chosen scope.

    `root` is the project when the answer was "this project only" and None when it
    was "every project". Codex still gets the text pasted rather than an import,
    because it documents no import syntax at either scope.
    """
    label, target, kind = AGENTS[key]
    if root is not None:
        target = root / PROJECT_FILES[key]
    return label, target, kind


def short(path) -> str:
    """`~/...` instead of the whole absolute path.

    The wizard shows a file path on every row of every question, and at full length
    they wrap and the list stops being readable at a glance. The `~` form is also
    what a person would type back.
    """
    text = str(path)
    home = str(Path.home())
    return "~" + text[len(home):] if text.startswith(home + "/") else text


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


def _write_agents(chosen: list[str], cmd: str, out, root: Path | None = None) -> None:
    block_file = instructions.block_path()
    for key in chosen:
        _, target, kind = target_for(key, root)
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


def _preview(chosen: list[str], cmd: str, out, root: Path | None = None) -> None:
    block_file = instructions.block_path()
    lines = instructions.render(cmd).strip().count("\n") + 1
    print("\nThis will change:", file=out)
    for key in chosen:
        _, target, kind = target_for(key, root)
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
    ap.add_argument("--scope", choices=SCOPES, default=None,
                    help="global: every project on this machine (default). "
                         "project: only the repository you are standing in")
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
    # Arrows need a terminal that can be put into raw mode. A test driving StringIO
    # and a CI job driving a pipe both take the numbered path, which is why every
    # test of these questions keeps working unchanged.
    keyboard = interactive and menu.has_keyboard(inp)
    flags_given = bool(args.agent or args.store or args.scope)
    root = _project_root()

    # 1. Scope. Asked only when there is a project to choose, and only when the
    #    answer would change something: outside a repository there is no second
    #    option to offer.
    scope = args.scope
    if scope is None:
        scope = "global"
        if root is not None and interactive and not args.agent:
            picked = menu.ask(
                "Where should this apply?",
                "The line is read by the agent, so this decides which projects see it.",
                [("project", "This project only", short(root)),
                 ("global", "Every project", "on this machine")],
                cursor=0, stdin=inp, out=out, keyboard=keyboard)
            scope = picked[0] if picked else "global"
    scope_root = root if scope == "project" else None
    if scope == "project" and root is None:
        print("--scope project needs a git repository; using the global files instead",
              file=out)
        scope_root = None

    # 2. Agents.
    chosen = list(dict.fromkeys(args.agent))
    if not chosen and interactive:
        where = f"in {short(scope_root)}" if scope_root else "for every project on this machine"
        chosen = menu.ask(
            "Which agents should use it?",
            f"The line goes into that agent's own instruction file, {where}.",
            [(key, target_for(key, scope_root)[0], short(target_for(key, scope_root)[1]))
             for key in ORDER] + [("", "none", "show me what to add and I will do it myself")],
            multi=True, cursor=0, stdin=inp, out=out, keyboard=keyboard)
        chosen = [key for key in chosen if key]

    if chosen:
        confirmed = args.yes or flags_given
        if not confirmed and interactive:
            _preview(chosen, cmd, out, scope_root)
            confirmed = menu.confirm("Write it?", stdin=inp, out=out, keyboard=keyboard)
            if not confirmed:
                print("nothing written", file=out)
        if confirmed:
            _write_agents(chosen, cmd, out, scope_root)
            print("\nStart a new agent session for it to take effect.", file=out)
        else:
            manual(cmd, out)
    else:
        manual(cmd, out)

    # 3. Where this project's pages live.
    if root is not None and (args.store or interactive):
        mode = args.store
        if mode is None:
            picked = menu.ask(
                f"Where should this project's memory pages live?   {short(root)}",
                "",
                [("gitignored", "Private", "appears on the first write, gitignored"),
                 ("tracked", "Committed", "reviewed in pull requests, shared with the team"),
                 ("home", "Outside the repo", f"~/.project-memory/{root.name}/ via a symlink")],
                cursor=0, stdin=inp, out=out, keyboard=keyboard)
            mode = picked[0] if picked else "gitignored"
        _apply_store(mode, root, out)

    if not interactive and not flags_given:
        print("\nNo terminal to confirm on, so nothing else was changed.", file=out)

    print(f"\nTo take it all back out:  {cmd} uninstall", file=out)
    return 0
