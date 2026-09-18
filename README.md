# project-memory

Durable project memory for coding agents: decisions, contracts and bug
post-mortems as **markdown pages on disk**, searchable without a server.

No server, no daemon, no API key, no hooks. The store is a `.memory/` directory
of `.md` files — greppable, diffable, reviewable in a pull request, and readable
by any agent or human. The runtime is Python 3.11+ standard library only, and
the same scripts run under Claude Code, Codex, Cursor, Gemini CLI, Kimi and
anything else that can run a shell command.

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

## Install: once per machine, or once per project

Two separate things get placed, and they have different scopes:

| | what it is | scope | where |
|---|---|---|---|
| **the skill** | code: the scripts and `SKILL.md` | **global** by default, once per machine; or local, committed with one repository | `~/.agents/skills/project-memory/` (global) or `<repo>/.agents/skills/project-memory/` (local) |
| **the store** | your notes | **always per project** | `<repo>/.memory/` |

The skill is one program and you install it once. The store is per project and
you never install it: it appears in a project the first time an agent writes
there, and is added to that project's `.gitignore` at that moment.

### Global: through your agent's plugin system

Each agent has its own plugin format, so this repository ships a manifest for
each one. Use your agent's native command; every one of these installs for
every project you will ever open.

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

**Anything else** — one command, once:
```bash
curl -fsSL https://raw.githubusercontent.com/Krowli/project-memory/main/install.sh | bash
```

It installs the **latest released tag**, not the tip of `main`, so the version it
prints means something and two people running it on the same day get the same
code. `PROJECT_MEMORY_REF=main` takes the branch instead. It places the skill in
`~/.agents/skills/`, which Codex and Cursor read natively, symlinks it into
`~/.claude/skills/` for Claude Code, verifies the scripts run, and stops. It
touches no agent's settings.

To update, run the same command again. To see whether that is worth doing:

```bash
./install.sh --check      # installed: 0.2.2 / latest: v0.3.0 / update: available
```

Every script also answers `--version`.

### Local: committed with one repository

```bash
cd your-project
curl -fsSL https://raw.githubusercontent.com/Krowli/project-memory/main/install.sh | bash -s -- --project
```

This puts the skill in `<repo>/.agents/skills/project-memory/` so it travels
with the repository, and — because it is now standing in a project — asks where
the store should live:

| mode | where | who can read it |
|---|---|---|
| `gitignored` *(default)* | `.memory/` in the project, added to `.gitignore` | only this machine |
| `tracked` | `.memory/` in the project, committed | anyone with repo access |
| `home` | `~/.project-memory/<project>/`, symlinked as `.memory/` | only this machine, and it cannot be committed by accident |

Pass `--store <mode>` to skip the question, or `--no-store` to install the skill
and nothing else. With no terminal to ask on — a pipeline, CI, a container — it
takes `gitignored` rather than guessing, because the mistake it prevents is
one-way: notes pushed to a remote cannot be unpublished. Choose `tracked`
deliberately, when you want the record reviewed in pull requests and shared
with the team, and you are confident nothing sensitive will land in it.

At runtime the scripts resolve the store as `$PROJECT_MEMORY_DIR` if set,
otherwise the nearest `.memory/` walking up from the working directory — so the
`home` mode's symlink works with no extra configuration.

## Make it automatic: one line per agent

There are no hooks. Earlier versions carried three Claude Code hooks — announce
the memory at session start, deny a hand-written page, remind a session that
changed files and wrote nothing — and every one of them existed on one harness.
A mechanism one agent has is not a mechanism, so the agent learns it has a
memory the way it learns any skill exists: from the skill's `description`,
which every harness that discovers skills shows the model at session start,
and from the instruction file it reads on every turn.

The description is in place as soon as the skill is installed. The instruction
file is the one thing you do by hand, once. The block lives inside the skill at
`skills/project-memory/USE.md`, so it travels with every install; where an agent
can include a file by path, point at it rather than copying it, because a copy
goes stale on the next release and nothing says so.

| agent | file to edit | what to add |
|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | `@~/.agents/skills/project-memory/USE.md` |
| Gemini CLI | `~/.gemini/GEMINI.md` | `@~/.agents/skills/project-memory/USE.md` |
| Codex CLI | `~/.codex/AGENTS.md` | the contents of `USE.md` — Codex documents no import syntax |
| Cursor | Customize → Rules | the contents of `USE.md` — the field takes text, not a path |

Claude Code expands `@path` imports, home-relative paths included, up to four
hops deep, and loads them from a user-scope file without an approval dialog.
Gemini CLI does the same with `@` in `GEMINI.md`. Adjust the path if you did not
install to the default location: `--project` puts the skill in
`.agents/skills/project-memory/`, and a clone of this repository has it at
`skills/project-memory/`.

**Where you put it decides who uses it**, which is the whole configuration
surface:

- one agent's or subagent's own description — only that agent searches and
  writes, which is what you want for a researcher or an analyst role;
- the project's `CLAUDE.md` or `AGENTS.md` — every agent working in that
  project, including subagents an orchestrator spawns there;
- the global file in the table — every agent in every project on the machine.

The store itself is per project, `.memory/` at its root, and every agent working
in that project shares it. One store for several projects is `--store home` or
`$PROJECT_MEMORY_DIR`.

This is how superpowers, the most widely installed skills library, runs on
Codex, Devin and Grok — nothing injected, the skill index is the trigger — and
it removed its own Codex hook because the native index worked better. The
survey, by primary sources, is in `docs/research/superpowers-portability.md`.

Whether an agent actually searches when nobody reminds it is the one thing this
cannot guarantee, on any harness. `evals/acceptance.py` is the proof: a real
session of the agent you name, a question only the store answers, and a check of
the store's log for the search. See [Measured](#measured).

**On Windows, mind the interpreter name.** `python3` is not a command Windows
has: the installer puts `python`, `py` and `pymanager` on PATH. The snippet
says `python3`; if that name does not resolve on your machine, replace it in
the copy you paste. `install.sh --interpreter py` verifies the install with a
particular interpreter. The scripts themselves are unaffected and the CI matrix
covers Windows.

## Usage

Search before answering, write after meaningful work:

```bash
memory_search.py "terminal freeze webgl context lost"     # ranked: slug — title — what matched — [score] updated
memory_search.py --touching src/terminal/renderer.ts     # the pages about this file, first
memory_write.py --slug webgl-context-loss \
  --title "xterm WebGL context loss on display sleep" \
  --kind bug --source src/terminal/renderer.ts --body - < page.md
memory_stats.py --since 2026-09-01                        # what the store has been doing
```

`--touching PATH` puts the pages whose `sources` cite that file, or anything
under that directory, ahead of every lexical hit, marked `▸ touches <path>`,
with or without query words. A file matches only itself, never its siblings.

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

The same floor is applied on read. A page that arrived around the script — by
hand, from another tool, from an agent whose harness cannot refuse a Write — is
skipped by search while it is under 200 characters, and named on stderr and in
`--json` so it can be rewritten through the script; a page with no sources is
shown, marked `⚠ no sources`. Search runs on every agent the skill is installed
in, which is what makes it the place for the check.

### The store keeps a log, and something reads it

Writes, refusals and queries are appended to `.memory/.log.jsonl`, each line
stamped with the session id the harness exports to the shell where one is
exported. The store carries its own `.gitignore` for that file, so it stays out
of commits under every store mode — it holds every query anyone typed.

```bash
memory_stats.py --since 2026-08-17
```
```
2026-08-17T18:31:03 … 2026-09-16T23:35:03

writes       24   (19 new, 5 merged, median 1536 chars)
refused       0   (0% of write attempts)
searches     41   (7% returned nothing)
            miss: terminal pane rendering Zenith Tauri
sessions      1   (0 searched and never wrote, 4.00 writes per session)
```

This is deliberately a pair. Collecting refusals without a reader would repeat
the exact failure the write gate exists to prevent: the system this replaced had
a reconcile pass that counted source rot correctly for months into a structure
with no consumer. A refusal rate concentrated on one code usually means the rule
is wrong rather than the writer; queries that return nothing point at either a
hole in the corpus or a hole in ranking; sessions that searched and never wrote
are the write side's "did it happen", with no hook collecting it.

## Measured

Every number below is reproducible from this repository: the corpus, the
queries, the methods and the scorer are committed under `evals/`, and the
commands that produce each table are listed at the end. Intervals are 95%
bootstrap over queries; comparisons between methods are paired. One caveat
applies to all of it: the 90-page corpus and its 270 queries were written by a
language model about a fictional project, not harvested from a real store. The
`paraphrase` query type exists to fight the obvious bias — a query written from
a page tends to reuse its words — but it does not remove it.

### Retrieval quality

nDCG@10 on 270 known-item queries over 90 pages.

| method | nDCG@10 | vs shipped, paired |
|---|---|---|
| **shipped (FTS5 index)** | **0.649** [0.600, 0.691] | — |
| shipped fallback, in-process BM25F | 0.644 | +0.004 [−0.009, +0.018], not a difference |
| title weight set to 0 | 0.595 | +0.054 [+0.027, +0.081] |
| term-count scoring, the previous ranker | 0.432 | +0.216 [+0.164, +0.267] |
| `grep -rilE`, unranked | 0.113 | +0.535 [+0.480, +0.586] |

By query type, shipped: keywords 0.792, paraphrase 0.532, prose 0.622. On 12
ambiguous queries with several relevant pages, 0.462. The two shipped paths
are indistinguishable in quality, which is what makes the index safe to prefer
for speed.

The most useful negative result: on 20 realistic questions that **no page
answers**, every method returned hits for all 20, and the top hit's score is
no different — median 9.93 for an answerable question against 8.73 for an
unanswerable one. A score threshold that removes a meaningful share of the
unanswerable set removes more of the answerable one. So the instruction to the
agent carries this instead: a result list is not evidence that an answer
exists.

### Searching by file

50 source paths, one per page, each relevant to every page that cites it.

| the path given as | nDCG@10 | R@1 |
|---|---|---|
| query words | 0.545 [0.450, 0.638] | 0.380 |
| `--touching` | 0.986 [0.965, 1.000] | 0.960 |

Paired +0.441 [+0.349, +0.539]. The second row is near the ceiling by
construction; the first is what typing the path costs today, and words cannot
recover it because 77 of the 90 pages never name a source file in title or body.

### Embeddings, measured and refused

The hybrid of BM25F with a transformer embedding
(`paraphrase-multilingual-MiniLM-L12-v2`, reciprocal rank fusion) is better:
**+0.046 [+0.014, +0.075]**. It is refused on cost, not quality: the skill is a
script run afresh per search, so the model loads every time — about 1 000 ms
and 1.06 GB resident against 72 ms for the whole shipped search. Static
embeddings, the cheapest form of the idea, were then measured to the same bar:

| model | on disk | hybrid vs shipped | cold process to a vector | peak RSS |
|---|---|---|---|---|
| `potion-base-8M` | 30 MB | +0.031 [−0.002, +0.063] | 527 ms | 143 MB |
| `potion-retrieval-32M` | 129 MB | +0.029 [−0.002, +0.063] | 585 ms | 355 MB |
| `potion-multilingual-128M` | 512 MB | +0.012 [−0.019, +0.042] | 2 218 ms | 1 842 MB |
| shipped search, whole, cold | — | — | 86 ms | 26 MB |

No interval clears zero and the cheapest cold start is six times the shipped
search. Dense retrieval is also worst exactly where it is supposed to win: on
paraphrase queries the transformer scores 0.347 against the lexical ranker's
0.532.

### Against the closest competitor

Basic Memory 0.22.1 — markdown on disk plus a persistent hybrid index with
local embeddings and a link graph — on the same pages, queries and scorer:
overall 0.640 against 0.649, paired **+0.009 [−0.040, +0.058], not
significant**. Keywords 0.830 against 0.792 in its favour, paraphrase 0.481
against 0.532 in this project's favour. Latency is deliberately not compared:
Basic Memory is designed to run as a long-lived server.

### Does it help the agent

`evals/agent_loop.json`: the corpus written out as a real store, 18 questions
in three families put to an agent with the store, the same questions minus the
store-only ones to a control agent without it, graded against gold facts fixed
before the answers existed.

| | with the store | control, no store |
|---|---|---|
| answerable (8) — the answer is in exactly one page | 8 correct | not run |
| unanswerable (5) — no page answers it | 5 abstained | 5 abstained |
| superseded (5) — a decision was reversed; asks what holds *now* | 5 correct, 0 obsolete | 5 abstained |

Median effort: 2 searches and 2 pages read when the answer exists, 6 searches
before concluding it does not. One run, one grader, a fictional project the
model cannot confabulate about; read the unanswerable row as an upper bound.

### Does the agent use it unprompted

`evals/acceptance.py`, 2026-09-16, no hook anywhere, no pointer file in the
project, one question only the store answers.

| how the agent was told | searches before answering | outcome | time |
|---|---|---|---|
| Claude Code, skill registered, no instruction file | 2 | answer named the decision | 19 s |
| Codex CLI 0.153, skill registered, user config and rules ignored | 1 | answer named the decision and followed the `superseded by` marker to the reversal | 24 s |
| Claude Code, **no skill registered**, one `@path` line in the project's `CLAUDE.md` | 1 | answer named the decision and its reversal | 24 s |

The third row is the one-line include on its own: nothing was registered with
the harness, and the import alone carried the instruction far enough for the
agent to search before answering. One run each, one question. Gemini, Cursor,
Kimi, Copilot, OpenCode and Pi are unmeasured until someone runs the same
command there.

### Speed, and the cost of the gate

End to end, as a shell invocation: 90 pages 235 ms reading every page against
99 ms with the warm index; 1 000 pages 1 887 against 174 ms; 5 000 pages
4 637 against 196 ms. A warm search is nearly flat in corpus size.

The write gate was tuned to a real population: 104 of 495 pages in the corpus
it was designed against were stubs averaging 139 characters, and they took the
top two result slots. Before the per-page lock, concurrent writers on one slug
— ordinary with subagent fan-out — lost up to 16 of 20 sections while every
command exited 0.

### Reproduce

```bash
python3 evals/run.py --by-type                 # retrieval, touching, ambiguous, unanswerable, calibration
python3 evals/dense_probe.py                   # needs fastembed; --static MODEL needs model2vec
python3 evals/compare_basic_memory.py          # needs basic-memory
python3 evals/acceptance.py --agent '...'      # a real agent session; see the file for commands
pytest                                         # 209 tests, both retrieval paths in CI
```

Every decision these numbers bought is also a page in this repository's own
`.memory/`, dated and sourced, including the two that refused something.

## Layout

```
skills/project-memory/     the skill itself — this is what gets installed
  SKILL.md                 instructions the agent loads
  scripts/                 memory_search.py, memory_write.py, memory_index.py,
                           memory_stats.py, memory_lib.py
  references/              detail loaded on demand, not at startup
  assets/                  page template
evals/                     reproducible retrieval measurement: corpus, queries, scorer;
                           acceptance.py runs a real agent session against the store
docs/research/             primary-source notes behind decisions
tests/                     pytest suite, stdlib only
.memory/                   this project's own pages, tracked on purpose
.claude-plugin/            plugin.json + marketplace.json
```

## Compatibility

| Agent | Mechanism | Verified |
|---|---|---|
| Claude Code | plugin marketplace, or `~/.claude/skills/` | yes, acceptance run |
| Codex | `~/.agents/skills/`, `$REPO_ROOT/.agents/skills` | yes, acceptance run |
| Cursor | `.agents/skills/`, `~/.agents/skills/` | per vendor docs |
| Gemini CLI | extension with `GEMINI.md` as its context file | per vendor docs |
| Kimi Code | plugin with `sessionStart.skill` | per vendor docs |
| Anything else | scripts + the `AGENTS.md` snippet | n/a |

`SKILL.md` frontmatter is restricted to the six fields in the
[Agent Skills spec](https://agentskills.io/specification) (`name`,
`description`, `license`, `compatibility`, `metadata`, `allowed-tools`), so the
same file loads in Claude Code and uploads to claude.ai unchanged. A CI test
enforces that restriction. The Claude Code path is checked in CI on every push
to `main`: `claude plugin validate --strict` for the manifests and the Agent
Skills spec validator for `SKILL.md`. The Python is tested on Ubuntu, macOS and
Windows against Python 3.11 and 3.13, on both retrieval paths.

## Contributing

`pytest` must be green and `ruff check .` clean. The version is carried in nine
places and a test fails if any of them drift: `.claude-plugin/plugin.json`,
`.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, `.kimi-plugin/plugin.json`,
`gemini-extension.json`, `pyproject.toml`, `SKILL.md`'s `metadata.version` and
`memory_lib.VERSION`. Bump them together, add a `CHANGELOG.md` entry, then tag:

```bash
git tag -a v0.3.0 -m "project-memory 0.3.0" && git push origin main v0.3.0
```

The tag triggers the release workflow, which checks the tag against the
manifests and publishes the changelog section as the GitHub release.

## License

MIT — see [LICENSE](LICENSE).
