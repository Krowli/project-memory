# project-memory

Durable project memory for coding agents: decisions, contracts and bug
post-mortems as **markdown pages on disk**, searchable without a server.

No server, no daemon, no API key. The store is a `.memory/` directory of `.md`
files — greppable, diffable, reviewable in a pull request, and readable by any
agent or human. The runtime is Python 3.11+ standard library only.

Search keeps a SQLite FTS5 index as a **cache**, in your cache directory rather
than in the store, and never in git. Delete it whenever you like: it rebuilds
itself, and if it cannot be used at all — no `sqlite3` in this Python, a
read-only checkout, a sibling process rebuilding it — the pages are read and
ranked directly instead. The markdown is always the source of truth.

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

**Anything else** — one command, once, for every project you will ever open:
```bash
curl -fsSL https://raw.githubusercontent.com/Krowli/project-memory/main/install.sh | bash
```

It installs the **latest released tag**, not the tip of `main`, so the version it
prints means something and two people running it on the same day get the same
code. `PROJECT_MEMORY_REF=main` takes the branch instead.

To update, run the same command again. To see whether that is worth doing:

```bash
./install.sh --check      # installed: 0.2.0 / latest: v0.2.0 / update: up to date
```

Every script also answers `--version`, and the session hook tells the agent which
version this project is running, because a `curl` install has no package manager
to ask.

Run it from anywhere. It installs the skill to `~/.agents/skills/`, registers the
two hooks, and stops there — a store is not something to set up per project,
it appears at the first write and shields itself as it is created.

To install into one repository instead, and commit the skill with it, add
`--project`. Add `--no-hook` to leave `settings.json` alone.

### It does not need to be introduced

A skill description is an invitation the model may decline; `hooks/` puts the
instruction into the session before the first turn, on startup and again after a
clear, a compact or a resume. You never say "we have a memory, use it" — the
agent already knows, and knows how many pages are in this project. Around 1.8 KB
of context, which is why it is a pointer and the full contract stays in
`SKILL.md`.

A second hook makes the write gate a gate. `PreToolUse` denies a direct Write or
Edit of a `.memory/*.md` page and names `memory_write.py` instead — without it,
"writes are refused, not requested" is itself a request, since the ordinary Write
tool walks straight around the validator. Set
`PROJECT_MEMORY_ALLOW_HAND_EDIT=1` to repair a page by hand deliberately.

Installed as a plugin, the agent picks up `hooks/hooks.json` itself. Installed
over `curl` there is no plugin system, so the installer writes both hooks into
`settings.json`, tagged `project-memory-session-start` and
`project-memory-write-guard` so they can be found and removed.

An agent that does not auto-discover skills needs only the scripts on disk plus
a pointer. Append [`AGENTS.md`](AGENTS.md) from this repo to your project's
`AGENTS.md` — that file is the whole integration.

### What is verified, and what is not

The Claude Code path is checked in CI on every push to `main` and on every
pull request: `claude plugin validate
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
python3 skills/project-memory/scripts/memory_write.py --slug hello \
  --title "First page" --kind concept --source README.md --body -   <<'PMEOF'
## Why this exists

A page has to carry something the source file cannot tell you on its own — the
reason behind a choice, the option that was rejected, the constraint that lives
outside the repository. Anything shorter than two hundred characters is refused
on the grounds that reading the code would have been faster, and this paragraph
exists mainly to clear that bar honestly.
PMEOF
python3 skills/project-memory/scripts/memory_search.py "first page"
```

## Usage

Search before answering, write after meaningful work:

```bash
memory_search.py "terminal freeze webgl context lost"     # ranked: slug — title — what matched — [score] updated
memory_write.py --slug webgl-context-loss \
  --title "xterm WebGL context loss on display sleep" \
  --kind bug --source src/terminal/renderer.ts --body - < page.md
```

Re-running `memory_write.py` with the same slug replaces same-header sections in
place and appends new ones, so repeated calls are safe and an amendment is cheap.
It prints `replaced:` and `appended:` for every section it touched.

When a decision reverses an earlier one, record the new page with
`--supersedes <old-slug>`. The old page is stamped `status: superseded`, scored at
half its rank and marked `⚠ superseded by <slug>` in every result line — it stays
searchable, because what was rejected and why is often the useful part, but it
stops outranking the page that replaced it. Recency is only a tie-break: equal
scores prefer the more recently updated page.

### Writes are refused, not requested

Asking an agent nicely, in a rules file, to keep a knowledge base tidy does not
work — measured on a real corpus, it produced 104 auto-generated stubs whose
bodies ran to about 139 characters (277 bytes on disk, frontmatter included), and
they then occupied the top two result slots for real queries. So the
check lives in the write path instead of in prose. `memory_write.py` exits
non-zero and prints a `FIX:` line naming the next command when a page has:

- no `--source`, or a `--source` path that does not exist on disk
- a resulting page under 200 characters — measured against the page that will
  exist, so a short amendment to a substantial page is fine while a thin new page
  is not
- an unknown `--kind` (`decision`, `bug`, `concept`, `howto`) or a slug that is
  not kebab-case
- `--supersedes` naming a slug that is not in the store

The correction then lands inside the agent's own tool loop, where it acts on it,
rather than in a document it may never read.

### The store keeps a log, and something reads it

Writes, refusals and queries are appended to `.memory/.log.jsonl`. The store
carries its own `.gitignore` for that file, so it stays out of commits under
every store mode — it holds every query anyone typed.

```bash
memory_stats.py --since 2026-08-09
```
```
2026-08-09T09:12:41 … 2026-08-17T16:04:03

writes       23   (19 new, 4 merged, median 812 chars)
refused       6   (21% of write attempts)
                4  body_too_short
                2  source_missing
searches     87   (9% returned nothing)
                miss: worktree detach race
```

This is deliberately a pair. Collecting refusals without a reader would repeat
the exact failure the write gate exists to prevent: the system this replaced had
a reconcile pass that counted source rot correctly for months into a structure
with no consumer. A refusal rate concentrated on one code usually means the rule
is wrong rather than the writer; queries that return nothing point at either a
hole in the corpus or a hole in ranking.

### Where the store lives, and who decides

Installing places two separate things, and they are not the same decision. The
**skill** is code: safe to commit, goes to `.agents/skills/`. The **store** is
whatever you write into it.

A default (user-scope) install does not create a store and does not ask about
one: it is not standing in any particular project, and it will meet many. A store
is created the first time an agent writes in a project, and is added to that
project's `.gitignore` at that moment — the one point where nobody has to
remember. `install.sh --project` is the run that asks, and can pick a different
mode up front:

| mode | where | who can read it |
|---|---|---|
| `gitignored` *(default)* | `.memory/` in the project, added to `.gitignore` | only this machine |
| `tracked` | `.memory/` in the project, committed | anyone with repo access |
| `home` | `~/.project-memory/<project>/`, symlinked as `.memory/` | only this machine, and it cannot be committed by accident |

Pass `--store <mode>` to skip the question, or `--no-store` to install the skill
and nothing else. With no terminal to ask on — a pipeline, CI, a container — it
takes `gitignored` rather than guessing, because the mistake it prevents is
one-way: notes pushed to a remote cannot be unpublished.

Choose `tracked` deliberately, when you want the record reviewed in pull
requests and shared with the team, and you are confident nothing sensitive will
land in it.

At runtime the scripts resolve the store as `$PROJECT_MEMORY_DIR` if set,
otherwise the nearest `.memory/` walking up from the working directory — so the
`home` mode's symlink works with no extra configuration.

## Layout

```
skills/project-memory/     the skill itself — this is what gets installed
  SKILL.md                 instructions the agent loads
  scripts/                 memory_search.py, memory_write.py, memory_index.py,
                           memory_stats.py, memory_lib.py
  references/              detail loaded on demand, not at startup
  assets/                  page template
hooks/                     session_start.py (announce), write_guard.py (enforce)
evals/                     reproducible retrieval measurement: corpus, queries, scorer
tests/                     pytest suite, stdlib only
.memory/                   this project's own pages, tracked on purpose
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

`pytest` must be green and `ruff check .` clean. The version is carried in eight
places and a test fails if any of them drift: `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, `.kimi-plugin/plugin.json`,
`gemini-extension.json`, `pyproject.toml` and `SKILL.md`'s `metadata.version`.
Bump them together, add a `CHANGELOG.md` entry, then tag:

```bash
claude plugin tag . --push        # creates project-memory--v0.1.0
git tag v0.1.0 && git push --tags # triggers the release workflow
```

## License

MIT — see [LICENSE](LICENSE).
