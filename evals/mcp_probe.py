#!/usr/bin/env python3
"""The probe is the shipped server now: `lore mcp`, run from this working tree.

    python3 evals/mcp_probe.py              # speak MCP on stdin/stdout
    python3 evals/mcp_probe.py --handshake  # what a client receives on initialize

This file used to carry the whole protocol so that MCP could be measured before
anything shipped. It measured 0/15 on Claude Code's defaults and 15/15 with the
deferral off — equal to the instruction file — and on those numbers the server was
kept out of the package. The decision since became the person's: `lore init` offers
MCP as a choice with the numbers on the question. So the protocol lives in
`pagelore.mcp`, and this is a wrapper kept for two callers that must keep working
without edits: `evals/acceptance.py --pointer mcp`, which points a `.mcp.json` at
this path, and the pages in `.memory/` that cite it. One implementation, measured
where it ships.

`--handshake` starts the server as a client would, as a separate process over its
real stdio, sends `initialize`, and reports the `instructions` the reply carries:
their size, and whether both tool names are in them. That is what can be checked
without a model; whether an agent then searches is `evals/acceptance.py --pointer mcp`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from pagelore import mcp  # noqa: E402


def handshake() -> int:
    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": mcp.PROTOCOL, "capabilities": {},
                          "clientInfo": {"name": "mcp_probe", "version": "0"}}}
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                          input=json.dumps(request) + "\n", capture_output=True,
                          text=True, encoding="utf-8", timeout=30)
    result = json.loads(proc.stdout.splitlines()[0])["result"]
    text = result.get("instructions") or ""
    names = {name: name in text for name in ("memory_search", "memory_write")}
    print(f"protocol      {result['protocolVersion']}")
    print(f"instructions  {len(text)} characters, {len(text.split())} words")
    for name, present in names.items():
        print(f"names         {name}: {'yes' if present else 'NO'}")
    return 0 if text and all(names.values()) else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--handshake"]:
        raise SystemExit(handshake())
    raise SystemExit(mcp.main(prog="mcp_probe"))
