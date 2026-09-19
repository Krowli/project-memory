"""`lore doctor` — the detector for the three states that produce no error.

Every failure this reports is silent by nature, which is the whole reason it
exists:

- **A dangling include.** The agent config points at a block that is not there.
  Claude Code and Gemini resolve a missing `@path` to nothing and say nothing; the
  agent simply stops searching, and nobody connects that to whatever deleted the
  file months earlier.
- **A stale paste.** Codex and Cursor cannot include a file, so they carry a copy
  that no upgrade can reach. It keeps telling the agent to run a command that may
  have moved on.
- **Nothing connected at all.** Measured, an agent with the block searches 15 times
  out of 15 and an agent without it never does. So "installed but not connected" is
  a fault, not a neutral state, and this exits non-zero to say so.

It also names the leftovers of the pre-0.4.0 layout, which nothing else will.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from . import __version__, instructions
from .cli import add_version
from .init import AGENTS
from .lib import find_store, page_paths

LEGACY_SKILL = Path.home() / ".agents" / "skills" / "project-memory"


def findings() -> list[dict]:
    out: list[dict] = []
    block = instructions.block_path()
    block_ok = block.is_file()
    out.append({"check": "block", "ok": block_ok, "detail": str(block) if block_ok
                else f"{block} is missing — run `lore init`"})

    connected = 0
    for key, (label, target, kind) in AGENTS.items():
        if not target.is_file():
            out.append({"check": f"agent:{key}", "ok": None,
                        "detail": f"{label}: no {target}"})
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        has = instructions.MARK_BEGIN in text or instructions.MARK_LEGACY in text
        if not has:
            out.append({"check": f"agent:{key}", "ok": None,
                        "detail": f"{label}: not connected ({target})"})
            continue
        connected += 1
        if instructions.MARK_LEGACY in text:
            out.append({"check": f"agent:{key}", "ok": False,
                        "detail": f"{label}: carries a pre-0.4.0 block — run `lore init` to replace it"})
        elif kind == "paste":
            stamped = re.search(r"pagelore (\d+\.\d+\.\d+)", text)
            version = stamped.group(1) if stamped else None
            fresh = version == __version__
            out.append({"check": f"agent:{key}", "ok": fresh,
                        "detail": f"{label}: pasted copy of {version or 'an unknown version'}"
                                  + ("" if fresh else f" — STALE, this install is {__version__};"
                                                      " run `lore init` again")})
        else:
            pointed = re.search(r"^@(\S+)", text[text.find(instructions.MARK_BEGIN):], re.M)
            target_ok = bool(pointed) and Path(pointed.group(1)).is_file()
            out.append({"check": f"agent:{key}", "ok": target_ok,
                        "detail": f"{label}: includes {pointed.group(1) if pointed else '?'}"
                                  + ("" if target_ok else " — that file is MISSING, the agent"
                                                          " silently loads nothing; run `lore init`")})

    out.append({"check": "connected", "ok": connected > 0,
                "detail": f"{connected} agent(s) connected"
                          + ("" if connected else " — nothing tells any agent the memory exists")})

    store = find_store()
    pages = len(page_paths(store)) if store.is_dir() else 0
    out.append({"check": "store", "ok": True,
                "detail": f"{store}: {pages} page(s)" if store.is_dir()
                          else f"{store} does not exist yet; the first write creates it"})

    command = shutil.which("lore") or shutil.which("pagelore")
    here = str(Path(__file__).resolve().parent)
    out.append({"check": "command", "ok": bool(command),
                "detail": f"{command} (this install: {here})" if command
                          else "neither `lore` nor `pagelore` is on PATH"})

    if LEGACY_SKILL.exists():
        out.append({"check": "legacy", "ok": False,
                    "detail": f"{LEGACY_SKILL} is left over from the skill-directory layout"
                              " and is safe to delete"})
    return out


def main(argv: list[str] | None = None, *, prog: str = "lore doctor") -> int:
    ap = argparse.ArgumentParser(prog=prog, description="Check this install.")
    add_version(ap)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    results = findings()
    if args.json:
        print(json.dumps({"version": __version__, "findings": results},
                         ensure_ascii=False, indent=2))
    else:
        for row in results:
            mark = {True: "ok  ", False: "FAIL", None: "--  "}[row["ok"]]
            print(f"{mark}  {row['detail']}")
    failed = any(row["ok"] is False for row in results)
    if failed and not args.json:
        print("\nSomething above is broken in a way that produces no error on its own.",
              file=sys.stderr)
    return 1 if failed else 0
