#!/usr/bin/env python3
"""Does an agent use the memory when nobody reminds it? Ask the agent.

    python3 evals/acceptance.py --agent 'claude --plugin-dir {repo} --setting-sources project
        --no-session-persistence --allowedTools "Bash(python3:*)" "Bash(cat:*)" Read -p {prompt}'
    python3 evals/acceptance.py --agent 'codex exec -C {project} --skip-git-repo-check
        --ephemeral --ignore-user-config --ignore-rules -s workspace-write {prompt}'

There is no hook anywhere in this skill, so the only thing that makes an agent
search before answering is the skill's own description in the harness's skill
index, or a pointer file the project carries. Whether that fires is not something
the code can guarantee; superpowers' porting guide reaches the same conclusion and
makes a real-session acceptance run the one proof. This is that run.

What it does: writes the evaluation corpus out as a real store inside a throwaway
project, links the skill where the harness discovers skills (`.agents/skills/`,
which Codex, Cursor, Gemini and Copilot read; Claude Code gets `--plugin-dir`),
runs the agent command once with a question only the store can answer, and then
reads the store's log. PASS means at least one search event landed before the
agent answered.

`--pointer` chooses how the instruction block reaches the agent, which is the
thing the README tells a user to set up:

  none      nothing but the skill itself; the description in the harness's skill
            index is the only trigger
  paste     the block transcribed into the project's CLAUDE.md, what a user does
            on a harness with no import syntax
  include   a one-line `@path` import of the installed USE.md, what a user does
            on Claude Code and Gemini — the line the README claims works
  mcp       no instruction block at all: the memory reached as MCP tools, whose
            names and descriptions the harness puts in front of the model by
            itself. Pass the agent an `--mcp-config {project}/.mcp.json`

`{prompt}`, `{project}` and `{repo}` are substituted into the agent command.
The command is split with shlex, so quote as you would in a shell.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import run as harness  # noqa: E402

# A prose query from the corpus whose answer is in exactly one page and nowhere
# else: the project is fictional, so nothing but the store can answer it.
QUESTION = ("This project's terminal does not use the graphics card to draw by default. "
            "Why was that decided? Answer in two sentences.")
RELEVANT = "render-canvas-default-renderer"


def build_project(directory: Path, pointer: str) -> Path:
    project = directory / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "main.ts").write_text("export {}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    harness.materialise(harness.load_corpus()["pages"], project)
    if pointer != "mcp":
        skills = project / ".agents" / "skills"
        skills.mkdir(parents=True)
        (skills / "project-memory").symlink_to(REPO / "skills" / "project-memory")
    use = REPO / "skills" / "project-memory" / "USE.md"
    if pointer == "paste":
        snippet = use.read_text(encoding="utf-8")
        snippet = snippet.replace("~/.agents/skills/", ".agents/skills/")
        (project / "CLAUDE.md").write_text(snippet, encoding="utf-8")
        (project / "AGENTS.md").write_text(snippet, encoding="utf-8")
    elif pointer == "include":
        # The path is absolute here because the skill under test is this working
        # tree rather than an install; a user writes the ~/ form the README gives.
        (project / "CLAUDE.md").write_text(f"@{use}\n", encoding="utf-8")
    elif pointer in ("mcp", "mcp+include"):
        if pointer == "mcp+include":
            (project / "CLAUDE.md").write_text(f"@{use}\n", encoding="utf-8")
        # Nothing tells the model the memory exists except the tool list, which
        # is the whole point of the comparison.
        (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"project-memory": {
            "type": "stdio", "command": sys.executable,
            "args": [str(HERE / "mcp_probe.py")],
            "env": {"PROJECT_MEMORY_DIR": str(project / ".memory")},
        }}}, indent=2), encoding="utf-8")
    return project


def log_events(store: Path) -> list[dict]:
    log = store / ".log.jsonl"
    if not log.exists():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--agent", required=True,
                    help="agent command with {prompt}, {project} and {repo} placeholders")
    ap.add_argument("--pointer", choices=("none", "paste", "include", "mcp", "mcp+include"), default="none",
                    help="how the memory reaches the agent (default: none)")
    ap.add_argument("--question", default=QUESTION)
    ap.add_argument("--keep", action="store_true", help="leave the project on disk")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="pm-acceptance-"))
    project = build_project(tmp, args.pointer)
    store = project / ".memory"
    before = len(log_events(store))

    cmd = [part.format(prompt=args.question, project=str(project), repo=str(REPO))
           for part in shlex.split(args.agent)]
    # A clean child: launched from inside an agent session, the session id and
    # nesting markers of the parent must not leak into the run being measured.
    env = {k: v for k, v in os.environ.items()
           if not (k.startswith("CLAUDE_CODE_") or k == "CLAUDECODE")}
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=project, capture_output=True, text=True,
                          timeout=args.timeout, env=env)
    elapsed = time.perf_counter() - started

    events = log_events(store)[before:]
    searches = [e for e in events if e.get("event") == "search"]
    writes = [e for e in events if e.get("event") == "write"]
    answer = proc.stdout.strip()
    mentions = RELEVANT.split("-")[1] in answer.lower()  # "canvas"

    print(f"agent      {' '.join(cmd[:2])}  (exit {proc.returncode}, {elapsed:.0f}s)")
    print(f"project    {project}  pointer={args.pointer}")
    print(f"searches   {len(searches)}" + (f"   first: {searches[0].get('query')!r}"
                                           if searches else ""))
    print(f"writes     {len(writes)}")
    print(f"answer     {answer[:300]!r}")
    verdict = "PASS" if searches else "FAIL"
    print(f"\n{verdict}: the agent {'searched the store before answering' if searches else 'answered without searching the store'}"
          + ("" if not searches else f"; answer {'names' if mentions else 'does not name'} the canvas decision"))
    if proc.returncode != 0:
        print(f"\nstderr:\n{proc.stderr[-2000:]}", file=sys.stderr)
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if searches else 1


if __name__ == "__main__":
    raise SystemExit(main())
