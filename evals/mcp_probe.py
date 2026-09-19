#!/usr/bin/env python3
"""A probe: the same memory, reached over MCP instead of by running a script.

    python3 evals/mcp_probe.py            # speak MCP on stdin/stdout

Not shipped, and not a second implementation. Every call lands in the functions
the CLI already calls, so retrieval quality cannot differ between the two — the
ranking, the index and the write gate do not move. What this exists to measure
is the other thing: whether an agent reaches for the memory more reliably when
the tools are in its tool list than when an instruction block tells it about a
command. `evals/acceptance.py --pointer mcp` runs that comparison.

Deliberately stdlib only and about a hundred lines of protocol, because the
question is whether the transport changes behaviour, not whether a dependency
can speak it. stdio transport: one JSON-RPC message per line, newline
delimited, nothing on stdout that is not a message — which is why every
diagnostic here goes to stderr.
"""
from __future__ import annotations

import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from pagelore import search as memory_search  # noqa: E402
from pagelore import write as memory_write  # noqa: E402
from pagelore.lib import find_store  # noqa: E402

PROTOCOL = "2025-06-18"

# The text the model sees before it has called anything. It is the skill's own
# trigger, worded for a tool list rather than for an instruction file: the
# comparison is only fair if both routes say the same thing about when to use it.
TOOLS = [
    {
        "name": "memory_search",
        "title": "Search project memory",
        "description": (
            "Search this project's durable memory: markdown pages recording decisions, "
            "rejected alternatives and the causes behind non-obvious bugs. Use before "
            "stating anything about this project — what it is, what it does, how a part "
            "works, why it is that way, what was decided or rejected — and before "
            "changing an unfamiliar subsystem. A hit marked 'superseded by' was replaced; "
            "read the replacement first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Several words; they are OR'd and ranked."},
                "touching": {"type": "array", "items": {"type": "string"},
                             "description": "File or directory paths: pages written "
                                            "against them come first."},
                "limit": {"type": "integer", "description": "Max results, default 10."},
            },
        },
    },
    {
        "name": "memory_write",
        "title": "Record a page in project memory",
        "description": (
            "Record what a future agent could not reconstruct from the code: the cause "
            "behind a symptom, the alternative that was rejected and why, a constraint "
            "from outside the repository. Use after an architectural decision, a "
            "non-obvious bugfix or a contract change; skip typos, reverts, formatting "
            "and test-only edits. Re-run the same slug to amend a page. A page that is "
            "not worth keeping is refused with the reason and the fix."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "kebab-case identifier."},
                "title": {"type": "string", "description": "One line."},
                "kind": {"type": "string", "enum": ["decision", "bug", "concept", "howto"]},
                "sources": {"type": "array", "items": {"type": "string"},
                            "description": "Files this page is about; each must exist."},
                "body": {"type": "string", "description": "Markdown, '## ' sections."},
                "supersedes": {"type": "array", "items": {"type": "string"},
                               "description": "Slugs this page replaces."},
            },
            "required": ["slug", "title", "kind", "sources", "body"],
        },
    },
]


def do_search(args: dict) -> tuple[str, bool]:
    store = find_store()
    hits = memory_search.search(args.get("query", ""), store,
                                k=int(args.get("limit", 10)),
                                touching=args.get("touching") or None)
    if not hits:
        return f"no matches in {store}", False
    lines = [f"{len(hits)} hit(s) in {store}"]
    lines += [memory_search.format_hit(s, p, args.get("query", "")) for s, p in hits]
    if memory_search.last_skipped:
        lines.append(memory_search.format_skipped(memory_search.last_skipped, store))
    return "\n".join(lines), False


def do_write(args: dict) -> tuple[str, bool]:
    """Straight through the CLI's own entry point, so the gate, the refusal codes
    and the FIX: lines are the ones the script produces rather than a second set
    that could drift from them."""
    argv = ["--slug", str(args.get("slug", "")), "--title", str(args.get("title", "")),
            "--kind", str(args.get("kind", "")), "--body", str(args.get("body", ""))]
    for source in args.get("sources") or []:
        argv += ["--source", str(source)]
    for slug in args.get("supersedes") or []:
        argv += ["--supersedes", str(slug)]

    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = memory_write.main(argv)
    text = (out.getvalue() + err.getvalue()).strip()
    return text or ("written" if code == 0 else "refused"), code != 0


def handle(message: dict) -> dict | None:
    method, mid = message.get("method"), message.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "project-memory", "version": "probe"},
        }}
    if method == "notifications/initialized":
        return None  # a notification carries no id and takes no answer
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        runner = {"memory_search": do_search, "memory_write": do_write}.get(name)
        if runner is None:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
        try:
            text, failed = runner(args)
        except Exception as exc:  # a crash must reach the model, not kill the server
            text, failed = f"{type(exc).__name__}: {exc}", True
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"content": [{"type": "text", "text": text}], "isError": failed}}
    if mid is None:
        return None  # any other notification
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle(message)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
