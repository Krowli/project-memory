"""`lore` — one command in front of the five modules that do the work.

A prefix router, deliberately not `argparse.add_subparsers()`. Three reasons, all
load-bearing:

- Subparsers re-declare every flag, and the refusal asymmetry would drift. `--kind`
  and `--body` are left unenforced on purpose so their absence produces a `reject()`
  with a `FIX:` line the agent acts on, while `--slug` and `--title` are `required=`
  and produce argparse's own usage error. Two shapes, both deliberate, neither
  survives being restated in a second parser.
- `lore write --body -` reads arbitrary text from stdin. A router hands `argv[1:]`
  through verbatim and cannot mangle it.
- The exit codes are the product. Routing preserves them by construction.

Each subcommand module is imported when it is dispatched to, not at startup: a
search must not pay for the wizard's prompt handling or the doctor's probes.
"""
from __future__ import annotations

import argparse
import importlib
import os
import platform
import sys
from pathlib import Path

from . import __version__

COMMANDS = ("search", "write", "stats", "init", "doctor", "uninstall")

# The two console scripts this package installs. `lore` is the documented name;
# `project-memory` is the escape hatch for a machine where something else already
# owns `lore`, and every message reflects whichever one was actually run.
NAMES = ("lore", "pagelore")


INVOKED_AS_ENV = "PAGELORE_INVOKED_AS"


def invoked_as() -> str:
    """Which of the two names was typed.

    A console script puts it in `argv[0]`. `python -m pagelore` puts `__main__.py`
    there instead, which is why the npm shim passes the name it was invoked by in
    the environment: it installs both names as links to one file, and the block it
    writes has to name the one that will still be there tomorrow.
    """
    named = os.environ.get(INVOKED_AS_ENV, "")
    if named in NAMES:
        return named
    name = Path(sys.argv[0] or NAMES[0]).name
    if name.endswith(".exe"):
        name = name[: -len(".exe")]
    return name if name in NAMES else NAMES[0]


def version_line(prog: str = "lore") -> str:
    """Version, which command answered, and from where.

    The install directory is not decoration: a user who installed through both pipx
    and npm has two `lore` on PATH, gets whichever the path order picks, and this
    line is the only thing that tells them which one just ran.
    """
    return (f"pagelore {__version__} ({prog}, python {platform.python_version()}, "
            f"{Path(__file__).resolve().parent})")


def add_version(ap: argparse.ArgumentParser) -> None:
    """One `--version` string for every subcommand, from one source.

    Deliberately not `importlib.metadata.version`: it raises in a bare clone, which
    is a supported way to run this, and the metadata is generated *from*
    `__version__` anyway, so reading it back can only agree or reveal a broken
    install. One test does that check; the runtime does not.
    """
    ap.add_argument("--version", action="version", version=version_line(ap.prog))


def usage(prog: str = "lore") -> str:
    """The command list, plus one line when nothing is connected yet.

    That line is paid for by a measurement. Fifteen sessions with the instruction
    block reachable searched before answering fifteen times; fifteen with nothing
    connected searched never. Before 0.4.0 a copied skill directory gave a harness
    something to index, and that alone was enough to make the agent search — so
    dropping the packaging removed a fallback, and this is the cheapest honest
    replacement: one `is_file()` check, on the one surface a person reads and an
    agent does not depend on.
    """
    from pagelore import instructions
    connected = instructions.block_path().is_file()
    return "\n".join([
        f"{prog} — durable project memory as markdown pages on disk",
        "",
        f"  {prog} search \"terminal freeze webgl context lost\"   find pages",
        f"  {prog} search --touching src/renderer.ts            pages about a file",
        f"  {prog} write --slug … --title … --kind … --source …  record one",
        f"  {prog} stats                                        what the store has been doing",
        f"  {prog} init                                         connect an agent to it",
        f"  {prog} doctor                                       check this install",
        f"  {prog} uninstall                                    disconnect it again",
        "",
        f"{prog} <command> --help for the flags of one command.",
    ] + ([] if connected else [
        "",
        f"Nothing is connected yet, so no agent knows this exists. Run `{prog} init`;",
        f"`{prog} doctor` says what is missing.",
    ]))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    prog = invoked_as()

    # Bare `lore` answers on stdout and exits 0. An agent probing whether the tool
    # exists must not read a non-zero exit as a broken install.
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage(prog))
        return 0
    if argv[0] in ("-V", "--version"):
        print(version_line(prog))
        return 0

    name, rest = argv[0], argv[1:]
    if name not in COMMANDS:
        print(f"{prog}: unknown command {name!r}", file=sys.stderr)
        # A `FIX:` line, because that is the one correction mechanism this product
        # has measured: the agent's loop already knows to follow it. So
        # `lore "why is auth server-side"` self-corrects instead of dead-ending.
        print(f"FIX: {prog} search {name!r}", file=sys.stderr)
        print(f"commands: {', '.join(COMMANDS)}", file=sys.stderr)
        return 2

    module = importlib.import_module(f"pagelore.{name}")
    try:
        return module.main(rest, prog=f"{prog} {name}")
    finally:
        # Housekeeping, after the subcommand's output and without touching its exit
        # code: bring the copy of the instruction block that agents include up to
        # this install's text. Never raises, never creates anything.
        from . import instructions
        instructions.refresh_quietly()


if __name__ == "__main__":
    raise SystemExit(main())
