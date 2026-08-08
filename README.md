# project-memory

Durable project memory for coding agents: decisions, contracts and bug
post-mortems as **markdown pages on disk**, searchable without a server.

No database, no daemon, no API key. The store is a `.memory/` directory of
`.md` files — greppable, diffable, reviewable in a pull request, and readable by
any agent or human. The runtime is Python 3.11+ standard library only.

## Why

Agents re-derive the same context every session and confidently restate
decisions that were reversed months ago. A memory store fixes that only if it is
cheap to write, cheap to read, and survives switching tools. Plain markdown in
git satisfies all three.

## Install

Each agent has its own plugin format, so this repository ships a manifest for
each one. Use your agent's native command.

**Claude Code**
```
/plugin marketplace add Krowli/project-memory
/plugin install project-memory@project-memory
```

**Codex CLI** — run `/plugins`, find `project-memory`, choose Install.

**Cursor**
```
/add-plugin project-memory
```

**Gemini CLI**
```bash
gemini extensions install https://github.com/Krowli/project-memory
```

**Kimi Code**
```
/plugins install https://github.com/Krowli/project-memory
```

**Anything else** — one command, drops the skill into `~/.agents/skills/`:
```bash
curl -fsSL https://raw.githubusercontent.com/Krowli/project-memory/main/install.sh | bash
```

Per-project instead of per-user (commit it alongside the repo):
```bash
curl -fsSL https://raw.githubusercontent.com/Krowli/project-memory/main/install.sh | bash -s -- --project
```

An agent that does not auto-discover skills needs only the scripts on disk plus
a pointer. Append [`AGENTS.md`](AGENTS.md) from this repo to your project's
`AGENTS.md` — that file is the whole integration.

### What is verified, and what is not

The Claude Code path is checked in CI on every push: `claude plugin validate
--strict` for the plugin manifests and the Agent Skills spec validator for
`SKILL.md`. The Python that both paths run is tested on Ubuntu, macOS and
Windows against Python 3.11 and 3.13.

The Codex, Cursor, Gemini and Kimi manifests are modelled on a widely-installed
skills repository's working manifests, and their shape is stable, but **no one
has yet installed this skill in those agents and watched it run**. If you do,
open an issue either way.

OpenCode and Pi are not supported yet: they need an executable extension in
JavaScript and TypeScript respectively, not just a manifest, and shipping code
that has never been executed is worse than shipping nothing.

### Evaluating from a cold clone

```bash
git clone https://github.com/Krowli/project-memory && cd project-memory
pip install -e ".[dev]" && pytest
```

Green suite, no network, no fixtures beyond `tmp_path`. To try it for real:

```bash
mkdir -p .memory
python3 skills/project-memory/scripts/memory_write.py --slug hello --title "First page"
python3 skills/project-memory/scripts/memory_search.py "first"
```

## Usage

Search before answering, write after meaningful work:

```bash
memory_search.py "terminal freeze webgl context lost"     # ranked slug — title — snippet
memory_write.py --slug webgl-context-loss \
  --title "xterm WebGL context loss on display sleep" \
  --kind bug --source src/terminal/renderer.ts
```

Re-running `memory_write.py` with the same slug replaces same-header sections
and appends new ones, so repeated calls are safe.

### Where the store lives

`$PROJECT_MEMORY_DIR` if set; otherwise the nearest `.memory/` directory walking
up from the working directory. Commit `.memory/` to version the record with the
code that motivated it.

## Layout

```
skills/project-memory/     the skill itself — this is what gets installed
  SKILL.md                 instructions the agent loads
  scripts/                 memory_search.py, memory_write.py, memory_lib.py
  references/              detail loaded on demand, not at startup
tests/                     pytest suite, stdlib only
.claude-plugin/            plugin.json + marketplace.json
```

## Compatibility

| Agent | Mechanism | Verified |
|---|---|---|
| Claude Code | plugin marketplace, or `~/.claude/skills/` | yes |
| Codex | `~/.agents/skills/`, `$REPO_ROOT/.agents/skills` | per vendor docs |
| Cursor | `.agents/skills/`, `~/.agents/skills/` | per vendor docs |
| Gemini CLI | `~/.agents/skills/` (alias of `~/.gemini/skills/`) | per vendor docs |
| Anything else | scripts + the `AGENTS.md` snippet | n/a |

`SKILL.md` frontmatter is restricted to the six fields in the
[Agent Skills spec](https://agentskills.io/specification) (`name`,
`description`, `license`, `compatibility`, `metadata`, `allowed-tools`), so the
same file loads in Claude Code and uploads to claude.ai unchanged. A CI test
enforces that restriction.

## Contributing

`pytest` must be green and `ruff check .` clean. Bump the version in
`.claude-plugin/plugin.json` **and** `.claude-plugin/marketplace.json` together
— a test fails if they drift — add a `CHANGELOG.md` entry, then tag:

```bash
claude plugin tag . --push        # creates project-memory--v0.1.0
git tag v0.1.0 && git push --tags # triggers the release workflow
```

## License

MIT — see [LICENSE](LICENSE).
