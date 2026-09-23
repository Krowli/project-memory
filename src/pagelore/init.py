"""`lore init` — connect an agent to the memory, and decide where a store lives.

Four questions, and nothing else. They are the only part of the old shell installer
that packaging does not subsume: pipx knows how to put a program on PATH and
nothing about which file an agent reads.

The fourth — how the agent reaches the memory — is the person's choice between the
instruction file and an MCP server, or both. It exists because the measurement that
kept MCP out of the package (0/15 searches on Claude Code's defaults, 15/15 with the
file; re-measured 3/5 on a later Claude Code) is an argument for a default, not for
deciding on someone's behalf. So the numbers sit on the question and the file stays
what Enter gives you.

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
import json
import shlex
import shutil
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
# How the agent reaches the memory: the instruction file, an MCP server, or both.
VIA = ("file", "mcp")
# The server's name in every harness's config — the name the measurement used.
MCP_SERVER = "project-memory"


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
    return "~" + text[len(home):] if text.startswith((home + "/", home + "\\")) else text


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

Or as an MCP server, in the agent's own tool list, instead of or as well as the file:

  Claude Code     {mcp_manual_command("claude", None, cmd)}
  Gemini CLI      {mcp_manual_command("gemini", None, cmd)}
  Codex CLI       {mcp_manual_command("codex", None, cmd)}

Or without questions:
  {cmd} init --agent claude --agent codex --yes
  {cmd} init --agent claude --via mcp --scope project --yes
  {cmd} init --store tracked --yes
""", file=out)


def report(label: str, value: str, out) -> None:
    """One line of what was done: `  updated   ~/.claude/CLAUDE.md`.

    Every report line goes through here so that they share one label column and
    one indent, and read as a block rather than as stray prints between menus.
    """
    print(f"  {label:<9} {value}", file=out)


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
            report(action, short(target), out)
        except OSError as exc:
            # One unwritable target must not abandon the others.
            report("skipped", f"{short(target)} ({exc})", out)


def _preview(chosen: list[str], cmd: str, out, root: Path | None = None,
             via: tuple[str, ...] = ("file",)) -> None:
    block_file = instructions.block_path()
    lines = instructions.render(cmd).strip().count("\n") + 1
    print("\n  This will change:", file=out)
    for key in chosen:
        if "file" in via:
            _, target, kind = target_for(key, root)
            print(f"    {short(target)}", file=out)
            if kind == "include":
                print(f"      + @{block_file}", file=out)
            else:
                print(f"      + the contents of {block_file} ({lines} lines)", file=out)
        if "mcp" in via:
            _, path, argv = mcp_target(key, root, cmd)
            if path is not None:
                print(f"    {short(path)}", file=out)
                print(f'      + mcpServers["{MCP_SERVER}"] → {cmd} mcp', file=out)
            else:
                why = "  (Codex keeps MCP servers globally)" if key == "codex" and root else ""
                print(f"    run  {_shell_line(argv)}{why}", file=out)
    print("", file=out)


# --- MCP: the other way an agent reaches the memory ---------------------------------
#
# Two mechanisms, for the same reason the file route has include and paste. Where
# the harness documents a plain JSON file that people edit by hand — Claude Code's
# `.mcp.json` in a project, Gemini's `settings.json` at either scope — the entry is
# merged into it here, and everything else in the file is left as it was. Where it
# does not — `~/.claude.json` is Claude Code's own state file and hand edits are
# undocumented; Codex's `config.toml` is TOML, which the standard library cannot
# write and, before 3.11, cannot read — the harness's own `mcp add` is run when the
# harness is on PATH, and printed for the person when it is not.
#
# The command written is the bare name this was run as, never an absolute path:
# `.mcp.json` is meant to be committed and shared, and a path into one person's
# home breaks it for everyone else. `lore doctor` checks the name is on PATH.


def mcp_entry(key: str, cmd: str) -> dict:
    """The server entry in that harness's own shape.

    Claude Code documents `type: "stdio"`; Gemini's schema has no `type` for stdio
    servers at all, so the field is left out rather than sent for it to reject.
    """
    entry = {"command": cmd, "args": ["mcp"]}
    return {"type": "stdio", **entry} if key == "claude" else entry


def mcp_target(key: str, root: Path | None, cmd: str) -> tuple[str, Path | None, list[str] | None]:
    """(label, JSON file to merge into, harness command to run) — exactly one of the
    last two is set. `root` is the project for "this project only" and None for
    "every project". Codex keeps MCP servers in ~/.codex/config.toml and nowhere
    else, so for it the scope is ignored and the preview says so."""
    label = AGENTS[key][0]
    if key == "claude":
        if root is not None:
            return label, root / ".mcp.json", None
        return label, None, ["claude", "mcp", "add", "--transport", "stdio", "--scope", "user",
                             MCP_SERVER, "--", cmd, "mcp"]
    if key == "gemini":
        base = root if root is not None else Path.home()
        return label, base / ".gemini" / "settings.json", None
    return label, None, ["codex", "mcp", "add", MCP_SERVER, "--", cmd, "mcp"]


def mcp_manual_command(key: str, root: Path | None, cmd: str) -> str:
    """The one line a person runs to do it themselves — printed when the harness is
    not on PATH, when a JSON file could not be parsed, and in the manual text."""
    scope = "project" if root is not None else "user"
    if key == "claude":
        return f"claude mcp add --transport stdio --scope {scope} {MCP_SERVER} -- {cmd} mcp"
    if key == "gemini":
        return f"gemini mcp add --scope {scope} {MCP_SERVER} {cmd} mcp"
    return f"codex mcp add {MCP_SERVER} -- {cmd} mcp"


def _shell_line(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


def _read_json(path: Path):
    """The parsed document, {} for a missing file, None when it is not plain JSON."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return None
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) else None


def merge_json_server(path: Path, entry: dict) -> str | None:
    """Fold our server into a JSON config, keeping everything else.

    Returns "wrote" when the file did not exist and "updated" when it did — even if
    the entry was already identical, because the person asked and the answer is
    what is there now — or None when the file is not plain JSON. Then nothing is
    written: a config someone keeps with comments in it is theirs to edit.
    """
    doc = _read_json(path)
    if doc is None:
        return None
    action = "updated" if path.exists() else "wrote"
    doc.setdefault("mcpServers", {})[MCP_SERVER] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return action


def registered_in_json(doc) -> dict | None:
    """Our entry under the top-level `mcpServers`, and only there.

    That is where `.mcp.json`, Gemini's settings.json and the user-scope half of
    ~/.claude.json keep servers. ~/.claude.json also nests local-scope servers under
    each project's path; those are not ours — this program never writes local scope
    — and a recursive walk would report another project's entry as this one's and
    then try to remove it. The shape is not documented, so it is not guessed: top
    level or nothing.
    """
    servers = doc.get("mcpServers") if isinstance(doc, dict) else None
    entry = servers.get(MCP_SERVER) if isinstance(servers, dict) else None
    return entry if isinstance(entry, dict) else None


def remove_json_server(path: Path) -> tuple[bool, bool]:
    """Take our entry out. Returns (changed, the document is now empty).

    An emptied `mcpServers` goes too, so a `.mcp.json` this program created reads
    as `{}` afterwards and the caller can delete it; whether to is the caller's
    call, because Gemini's settings.json is never ours to delete. A file that is
    not plain JSON is left alone.
    """
    doc = _read_json(path)
    if not doc or registered_in_json(doc) is None:
        return False, False
    del doc["mcpServers"][MCP_SERVER]
    if not doc["mcpServers"]:
        del doc["mcpServers"]
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True, not doc


def codex_registered(config_toml: Path) -> str | None:
    """The `command` of our server in Codex's config.toml; "" when the table is there
    but the command is not readable; None when it is not registered.

    A regex, not a TOML parser: the standard library has no parser before 3.11 and
    no writer at all, and the two lines this needs are the table header and the
    `command = "…"` under it.
    """
    try:
        lines = config_toml.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    inside = seen = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            inside = stripped in (f"[mcp_servers.{MCP_SERVER}]", f'[mcp_servers."{MCP_SERVER}"]')
            seen = seen or inside
            continue
        if inside and stripped.startswith("command"):
            _, _, value = stripped.partition("=")
            return value.strip().strip('"').strip("'")
    return "" if seen else None


def _run_or_print(argv: list[str], out) -> bool:
    """The harness's own `mcp add` / `mcp remove`, when the harness is here to run it.

    Otherwise the line is printed for the person: the two files behind these
    commands, ~/.claude.json and ~/.codex/config.toml, are not ours to edit by hand.
    A failure is reported with the harness's first line and the command to retry —
    never hidden, because the next thing the person sees would be an agent that
    does not have the tools they were told it had.
    """
    line = _shell_line(argv)
    exe = shutil.which(argv[0])
    if exe is None:
        report("run", f"{line}   ({argv[0]} is not on PATH here, so do this yourself)", out)
        return False
    try:
        proc = subprocess.run([exe, *argv[1:]], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        report("skipped", f"{argv[0]} could not be run ({exc})", out)
        report("run", line, out)
        return False
    verb = argv[2]
    if proc.returncode == 0:
        report("added" if verb == "add" else "removed", f"{MCP_SERVER} via {argv[0]} mcp {verb}", out)
        return True
    said = (proc.stderr or proc.stdout).strip().splitlines()
    report("skipped", f"{argv[0]} exited {proc.returncode}: {said[0] if said else 'no output'}", out)
    report("run", line, out)
    return False


def _write_mcp(chosen: list[str], cmd: str, out, root: Path | None) -> None:
    for key in chosen:
        _, path, argv = mcp_target(key, root, cmd)
        if argv is not None:
            _run_or_print(argv, out)
            continue
        action = merge_json_server(path, mcp_entry(key, cmd))
        if action is None:
            report("skipped", f"{short(path)} is not plain JSON; left alone", out)
            report("run", mcp_manual_command(key, root, cmd), out)
        else:
            report(action, short(path), out)
    if "claude" in chosen and root is not None:
        report("note", "Claude Code asks once to approve the project's .mcp.json; "
                       "run /mcp in a session to do it", out)


def _apply_store(mode: str, root: Path, out) -> None:
    store = root / ".memory"
    if mode == "gitignored":
        # Deliberately creates nothing: the first write creates the store and
        # shields it as it does. A machine-setup command that makes a directory
        # inside someone's repository is a surprise, and this one would be useless.
        report("store", f"{short(store)}  appears on the first write, gitignored", out)
        return
    if mode == "tracked":
        # Must act now. `.tracked` has to exist before the first write, or the
        # store gitignores itself behind a user who asked for the opposite.
        store.mkdir(parents=True, exist_ok=True)
        (store / TRACKED_MARKER).write_text(
            "These pages are committed on purpose. Do not gitignore this store.\n",
            encoding="utf-8")
        report("store", f"{short(store)}  committed with the repo; do not write secrets here",
               out)
        return
    # `instructions.home()`, not `Path.home() / ".project-memory"`: the same directory
    # by default, but one place decides where it is. Two computations of one path drift,
    # and this one drifted in the only way that matters — it could not be redirected, so
    # a test of this mode wrote into the real home directory on a CI machine.
    target = instructions.home() / root.name
    target.mkdir(parents=True, exist_ok=True)
    if store.exists() and not store.is_symlink():
        report("note", f"{short(store)} already exists as a real directory; leaving it alone.",
               out)
        report("", f"Move its contents to {short(target)} and delete it to finish the switch.",
               out)
        return
    if store.is_symlink():
        store.unlink()
    store.symlink_to(target)
    _ignore(root, out)
    report("store", f"{short(target)}  outside the repo, reached through the .memory/ symlink",
           out)


def _ignore(root: Path, out) -> None:
    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if any(line.strip().strip("/") == ".memory" for line in existing.splitlines()):
        return
    prefix = "" if (not existing or existing.endswith("\n")) else "\n"
    with gitignore.open("a", encoding="utf-8") as fh:
        fh.write(f"{prefix}\n# project-memory: notes stay local\n.memory/\n")
    report("ignored", ".memory/ added to .gitignore", out)


def main(argv: list[str] | None = None, *, prog: str = "lore init",
         stdin=None, stdout=None, interactive: bool | None = None) -> int:
    ap = argparse.ArgumentParser(prog=prog, description="Connect an agent to the memory.")
    add_version(ap)
    ap.add_argument("--agent", action="append", default=[], choices=sorted(AGENTS),
                    help="connect this agent; repeatable; implies --yes")
    ap.add_argument("--scope", choices=SCOPES, default=None,
                    help="global: every project on this machine (default). "
                         "project: only the repository you are standing in")
    ap.add_argument("--via", action="append", default=[], choices=VIA,
                    help="how the agent reaches it: file (an @-line in its instruction file, "
                         "the default) or mcp (a stdio server in its tool list); repeatable")
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
    print(f"{prog}  ·  block at {short(block_file)}\n", file=out)

    if args.show:
        print(f"@{block_file}", file=out)
        return 0

    if interactive is None:
        interactive = bool(getattr(inp, "isatty", lambda: False)()) and not args.yes
    # Arrows need a terminal that can be put into raw mode. A test driving StringIO
    # and a CI job driving a pipe both take the numbered path, which is why every
    # test of these questions keeps working unchanged.
    keyboard = interactive and menu.has_keyboard(inp)
    flags_given = bool(args.agent or args.store or args.scope or args.via)
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
        # 3. How the agent reaches it. The numbers are on the question rather than in
        #    the README because this is only a choice if what was measured is in front
        #    of the person as they make it. Enter keeps the file: the measured default.
        via = tuple(dict.fromkeys(args.via))
        if not via and interactive:
            via = tuple(menu.ask(
                "How should the agent reach it?",
                "Enter keeps the file. Measured: file 15/15; MCP alone 0/15, later 3/5.",
                [("file", "Instruction file", "one @-line the agent reads every turn"),
                 ("mcp", "MCP server", "in its tool list, deferred by default on Claude Code")],
                multi=True, cursor=0, stdin=inp, out=out, keyboard=keyboard))
        via = via or ("file",)

        confirmed = args.yes or flags_given
        if not confirmed and interactive:
            _preview(chosen, cmd, out, scope_root, via)
            confirmed = menu.confirm("Write it?", stdin=inp, out=out, keyboard=keyboard)
            if not confirmed:
                print("nothing written", file=out)
        if confirmed:
            if "file" in via:
                _write_agents(chosen, cmd, out, scope_root)
            if "mcp" in via:
                _write_mcp(chosen, cmd, out, scope_root)
                if via == ("mcp",) and "claude" in chosen:
                    report("note", "measured on Claude Code: MCP alone searched 0/15 at default "
                                   "settings in 2026-09, 3/5 on a later version;", out)
                    report("", "every time with ENABLE_TOOL_SEARCH=false, or with the "
                               "instruction file as well", out)
            print("\nStart a new agent session for it to take effect.\n", file=out)
        else:
            manual(cmd, out)
    else:
        manual(cmd, out)

    # 3. Where this project's pages live.
    if root is not None and (args.store or interactive):
        mode = args.store
        if mode is None:
            picked = menu.ask(
                "Where should this project's memory pages live?",
                short(root),
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
