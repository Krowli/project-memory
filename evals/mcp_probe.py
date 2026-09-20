#!/usr/bin/env python3
"""The probe is the shipped server now: `lore mcp`, run from this working tree.

    python3 evals/mcp_probe.py            # speak MCP on stdin/stdout

This file used to carry the whole protocol so that MCP could be measured before
anything shipped. It measured 0/15 on Claude Code's defaults and 15/15 with the
deferral off — equal to the instruction file — and on those numbers the server was
kept out of the package. The decision since became the person's: `lore init` offers
MCP as a choice with the numbers on the question. So the protocol lives in
`pagelore.mcp`, and this is a wrapper kept for two callers that must keep working
without edits: `evals/acceptance.py --pointer mcp`, which points a `.mcp.json` at
this path, and the pages in `.memory/` that cite it. One implementation, measured
where it ships.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from pagelore import mcp  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(mcp.main(prog="mcp_probe"))
