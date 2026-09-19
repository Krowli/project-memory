# pagelore

Durable project memory for coding agents: decisions, contracts and bug
post-mortems as **markdown pages on disk**, searchable without a server.

```bash
pipx install pagelore        # or: npm install -g pagelore
lore init
```

The store is a `.memory/` directory of `.md` files — greppable, diffable,
reviewable in a pull request, readable by any agent or human. No server, no
daemon, no API key, no hooks. The runtime is the Python 3.9+ standard library,
the version a stock macOS already ships, and the same command runs under Claude
Code, Codex, Cursor, Gemini CLI, Kimi and anything else that can run a shell
command.

Search keeps a SQLite FTS5 index as a **cache**, in your cache directory rather
than in the store, and never in git. Delete it whenever you like: it rebuilds
itself, and if it cannot be used at all — no `sqlite3` in this Python, a
read-only checkout, a sibling process rebuilding it — the pages are read and
ranked directly instead. The markdown is always the source of truth.

The package is `pagelore` and the command is `lore` because `project-memory` and
`pm` were both already taken on PyPI and on npm, by unrelated products in the
same niche. Versions up to 0.3.5 were installed as a copied skill directory; that
is [gone](#upgrading-from-03x), and the release notes say what to do about it.

## Why

Agents re-derive the same context every session and confidently restate
decisions that were reversed months ago. A memory store fixes that only if it is
cheap to write, cheap to read, and survives switching tools. Plain markdown in
git satisfies all three.

## Install

Either package manager installs the same program. Pick the one you already have.

```bash
pipx install pagelore          # Python. `pip install --user pagelore` also works
npm install -g pagelore        # Node. Vendors the Python; runs no pip, no postinstall
```

Then, once per machine:

```bash
lore init
```

`lore init` does three things, in this order, and nothing else:

1. Writes the instruction block to `~/.project-memory/AGENT.md`. This is the text
   that makes an agent search before it answers, and it is the only part that is
   not optional — [measured](#does-the-agent-use-it-unprompted), an agent with it
   searches every time and an agent without it never does.
2. Asks which agents should use it, and offers to add one line to that agent's own
   instruction file. It prints the exact file and the exact line first, then asks.
   **The default connects nothing** — writing into your global agent configuration
   unasked is not a default anyone else gets to choose for you. If you decline it
   prints the line so you can add it yourself.
3. Inside a git repository, asks whether this project's pages should be private
   (gitignored, the default) or tracked and reviewed in pull requests.

With no terminal to answer on it asks nothing, writes only the block, prints the
manual instructions and exits 0. Flags are the confirmation, so a scripted install
works:

```bash
lore init --agent claude --store tracked --yes
```

To check what is connected, and to catch the three failures that produce no error
on their own — an include pointing at a file that is gone, a pasted copy left
behind by an older version, a leftover skill directory:

```bash
lore doctor
```

### The one line, per agent

The line points at a file rather than carrying the text, because a transcription
is a fork: the next release changes the block, every pasted copy stays as it was,
and nothing anywhere says so. The file is refreshed by every `lore` invocation,
which costs about 50 µs against a 50 ms search.

| Agent | File | What goes in it |
|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | `@~/.project-memory/AGENT.md` |
| Gemini CLI | `~/.gemini/GEMINI.md` | `@~/.project-memory/AGENT.md` |
| Codex CLI | `~/.codex/AGENTS.md` | the block's text, pasted |
| Cursor | Settings → Rules → User Rules | the block's text, pasted |
| Anything else | whatever it reads every turn | either, if it expands `@path` |

Claude Code expands `@path`, home-relative paths included, four hops deep, and
loads a user-scope file's imports without an approval dialog. Gemini CLI takes the
same syntax. Codex documents no import syntax and Cursor's User Rules is a text
field, so those two get the text; the block carries a version stamp in an HTML
comment, and `lore doctor` reports a pasted copy that has gone stale. Claude Code
strips block-level comments before injection, so the stamp costs the agent nothing.

A project can override the global answer: put the same line, or a narrower one, in
that repository's own `CLAUDE.md` or `AGENTS.md`.

### Updating

```bash
pipx upgrade pagelore          # or: npm update -g pagelore
```

The instruction block is refreshed by the next `lore` command you or your agent
runs, so there is nothing to re-copy. A pasted copy is the exception, and is why
`lore doctor` exists.

### Removing it

```bash
lore uninstall                 # takes the block back out of every file it was added to
pipx uninstall pagelore        # or: npm uninstall -g pagelore
```

In that order. `pipx uninstall` cannot run our code, so it leaves the fenced block
behind as an include pointing at a file nothing will ever recreate — and an agent
that cannot load an `@path` does not error, it just stops searching. `lore
uninstall` removes only the fenced block and leaves everything you wrote around
it. **Your pages are never touched**, by this or by anything else; delete a
`.memory/` directory yourself if you mean to.

### Upgrading from 0.3.x

0.3.x installed a skill directory and wrote a line pointing into it. That
directory is gone, so do this once, in this order:

```bash
sh install.sh --uninstall      # or re-run the curl one-liner; it now only uninstalls
pipx install pagelore
lore init
```

`lore init` also recognises and replaces the old marker, so if you forget the
first step you get one block rather than two. What it cannot fix is a plugin or
extension install, which is separate:

```
Claude Code   /plugin uninstall project-memory
Gemini CLI    gemini extensions uninstall project-memory
Codex, Cursor, Kimi   remove the directory you pointed them at
```

## Usage

Search before answering, write after meaningful work:

```bash
lore search "terminal freeze webgl context lost"     # ranked: slug — title — what matched — [score] updated
lore search --touching src/terminal/renderer.ts      # the pages about this file, first
lore write --slug webgl-context-loss \
  --title "xterm WebGL context loss on display sleep" \
  --kind bug --source src/terminal/renderer.ts --body - < page.md
lore stats --since 2026-09-01                        # what the store has been doing
```

A bare `lore` prints the command list and exits 0, because an agent checking
whether the tool exists must not read a non-zero exit as a broken install. An
unknown command prints a `FIX:` line naming the one you probably meant.

`--touching PATH` puts the pages whose `sources` cite that file, or anything
under that directory, ahead of every lexical hit, marked `▸ touches <path>`,
with or without query words. A file matches only itself, never its siblings.

Re-running `lore write` with the same slug replaces same-header sections in
place and appends new ones, so repeated calls are safe and an amendment is cheap.
It prints `replaced:` and `appended:` for every section it touched.

When a decision reverses an earlier one, record the new page with
`--supersedes <old-slug>`. The old page is stamped `status: superseded`, scored at
half its rank and marked `⚠ superseded by <slug>` in every result line — it stays
searchable, because what was rejected and why is often the useful part, but it
stops outranking the page that replaced it. Recency is only a tie-break: equal
scores prefer the more recently updated page.

If you would rather grant an agent a narrow permission than arbitrary Python, the
whole surface is one program: `Bash(lore:*)` in Claude Code, and the equivalent
elsewhere.

### Writes are refused, not requested

Asking an agent nicely, in a rules file, to keep a knowledge base tidy does not
work — measured on a real corpus, it produced 104 auto-generated stubs whose
bodies ran to about 139 characters (277 bytes on disk, frontmatter included), and
they then occupied the top two result slots for real queries. So the check lives
in the write path instead of in prose. `lore write` exits non-zero and prints a
`FIX:` line naming the next command when a page has:

- no `--source`, or a `--source` path that does not exist on disk
- a resulting page under 200 characters — measured against the page that will
  exist, so a short amendment to a substantial page is fine while a thin new page
  is not
- an unknown `--kind` (`decision`, `bug`, `concept`, `howto`) or a slug that is
  not kebab-case
- `--supersedes` naming a slug that is not in the store

The correction then lands inside the agent's own tool loop, where it acts on it,
rather than in a document it may never read.

The same floor is applied on read. A page that arrived around the command — by
hand, from another tool, from an agent whose harness cannot refuse a Write — is
skipped by search while it is under 200 characters, and named on stderr and in
`--json` so it can be rewritten properly; a page with no sources is shown, marked
`⚠ no sources`. Search runs on every agent, which is what makes it the place for
the check.

### The store keeps a log, and something reads it

Writes, refusals and queries are appended to `.memory/.log.jsonl`, each line
stamped with the session id the harness exports to the shell where one is
exported. The store carries its own `.gitignore` for that file, so it stays out
of commits under every store mode — it holds every query anyone typed.

```bash
lore stats --since 2026-08-17
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

This is the measurement the product lives on, because nothing here fires by
itself: no hook, and since 0.4.0 no skill manifest for a harness to index either.
The only thing that makes an agent search before it answers is the instruction
block. `evals/acceptance.py` puts one question to a real session in a throwaway
project whose store holds the answer, and reads the store's log afterwards. A run
passes only if a search landed **before** the answer.

Fifteen sessions per arm, Claude Code 2.1.278, 2026-09-19, one question that never
says "why":

| how the agent learns the memory exists | searched before answering |
|---|---|
| the one `@path` line in `CLAUDE.md` | **15 / 15** |
| nothing at all — no line, no manifest, no tools | **0 / 15** |
| before 0.4.0: a registered skill directory, no instruction line | **15 / 15** |

The second row is a control that cannot pass, which is what makes the first row
mean anything. It is also the honest floor: install this and connect nothing, and
you have installed nothing. `lore doctor` therefore calls "installed but not
connected" a fault rather than a neutral state.

The third row is the one this repackage has to answer for, and it does not say
what was hoped. Up to 0.3.5 the program shipped as a skill directory a harness
could index, and that description alone made the agent search 15 times out of 15
with no instruction line anywhere. So dropping the packaging removed a fallback
that worked, for the specific user who installs and then connects nothing. The
recommended setup is 15/15 either way, which is why the trade was taken; what
pays for it is that `lore init` runs at install time and offers the line, `lore
doctor` calls an unconnected install a fault rather than a neutral state, and a
bare `lore` says so in one line. None of those existed when the skill directory
was doing the work.

One earlier single run covers a harness the 15-run arms do not: Codex CLI 0.153,
the block pasted into its rules, searched once and its answer followed the
`superseded by` marker to the reversal. Gemini, Cursor, Kimi, Copilot, OpenCode and
Pi are unmeasured until someone runs the same command there.

### MCP, measured and refused

An MCP server here is a wrapper: it calls the same two functions, so retrieval
quality cannot differ. The claim to test was the other one — that an agent
reaches for the memory more reliably when the tools are in its tool list than
when an instruction file tells it about a command. `evals/mcp_probe.py` is that
server, stdlib only; `evals/acceptance.py --pointer mcp|include|mcp+include`
runs it. Fifteen real sessions per arm on a task-shaped prompt that never says
"why", where the store holds the decision and its reversal.

| how the agent learns the memory exists | searched before answering |
|---|---|
| one `@path` line in the project's `CLAUDE.md` | 15 / 15 |
| MCP tools, Claude Code's default settings | **0 / 15** |
| MCP tools, `ENABLE_TOOL_SEARCH=false` | 15 / 15 |
| MCP tools plus the `@path` line | 15 / 15 |

The zero is not a model ignoring a tool it can see. Claude Code defers MCP tools
behind tool search by default, so they are not in the tool list at session start
at all, and the one advantage MCP was supposed to have does not exist out of the
box. With the deferral turned off it matches the instruction line exactly and
never beats it; added on top of it, it changes nothing.

So MCP is not shipped. It would cost a config entry in each agent's own format
against one copied directory, a process per session, and context for a tool
list, and it buys nothing measurable. The probe stays in `evals/` so the
question can be re-run rather than re-argued.


### Speed, and the cost of the gate

One search, end to end, as the command a user types: a fresh process, interpreter
startup included. `python3 evals/speed.py` produces this table, and `--pages`
changes the sizes. The corpus is the committed 90 pages grown by suffixing slugs.

| pages | warm, with the index | index refused | ratio |
|---|---|---|---|
| 90 | 52 ms | 76 ms | 1.5× |
| 1 000 | 69 ms | 341 ms | 4.9× |
| 5 000 | 139 ms | 1 507 ms | 10.8× |

The second column is not a hypothetical: it is what happens on a read-only
checkout, on a Python without `sqlite3`, and while a sibling process rebuilds the
index. That it stays usable to 1 000 pages is why the index is allowed to be a
disposable cache rather than the store.

Cold start by install route, same query, 90 pages:

| route | median |
|---|---|
| `lore`, installed by pipx | 52 ms |
| `python -m pagelore` | 52 ms |
| `lore`, installed by npm | 87 ms |

The npm route pays for a Node process that then spawns Python. It spawns the first
candidate interpreter with the real arguments rather than probing with a throwaway
`--version` first, because that probe would have added a second round trip to
every search.

Figures published before 0.4.0 came from an uncommitted script and are superseded,
not comparable: the measurement is in the repository now, which is the point.

The write gate was tuned to a real population: 104 of 495 pages in the corpus it
was designed against were stubs averaging 139 characters, and they took the top
two result slots. Before the per-page lock, concurrent writers on one slug —
ordinary with subagent fan-out — lost up to 16 of 20 sections while every command
exited 0.

### Reproduce

```bash
python3 evals/run.py --by-type                 # retrieval, touching, ambiguous, unanswerable, calibration
python3 evals/speed.py                         # the table above
python3 evals/dense_probe.py                   # needs fastembed; --static MODEL needs model2vec
python3 evals/compare_basic_memory.py          # needs basic-memory
python3 evals/acceptance.py --pointer include --agent '...'   # a real agent session
python3 evals/acceptance.py --pointer mcp --agent '...'       # the same session over MCP
pytest                                         # both retrieval paths, in CI on three operating systems
```

`evals/acceptance.py` needs `lore` on PATH and refuses to run without it: an agent
that tries to search and cannot would score the same as one that never tried.

Every decision these numbers bought is also a page in this repository's own
`.memory/`, dated and sourced, including the ones that refused something.

## Layout

```
src/pagelore/              the program
  cli.py                   the dispatcher: one prefix router, not argparse subcommands
  search.py index.py       ranking, and the FTS5 index that is a cache
  write.py lib.py stats.py the write gate, the store, the log reader
  init.py doctor.py        the wizard, and the detector for what has gone silently wrong
  instructions.py          renders and refreshes the block an agent reads every turn
  data/AGENT.md            that block — the measured 15/15 text
npm/                       the Node route: a shim, plus src/pagelore vendored at pack time
docs/                      page format, retrieval detail, and primary-source research notes
evals/                     reproducible measurement: corpus, queries, scorer, speed,
                           an MCP probe, and a real-agent acceptance run
tests/                     pytest suite, stdlib only
tools/                     one-shot maintenance scripts
.memory/                   this project's own pages, tracked on purpose
install.sh                 retired; it now only prints the new commands and uninstalls 0.3.x
```

## Compatibility

One installed command, so there is no per-agent mechanism left to get wrong — only
the line that tells the agent about it.

| Agent | How it learns the memory exists | Verified |
|---|---|---|
| Claude Code | `@~/.project-memory/AGENT.md` in `CLAUDE.md` | yes, 15 of 15 acceptance sessions |
| Codex CLI | the block pasted into `~/.codex/AGENTS.md` | yes, acceptance run on 0.153 |
| Gemini CLI | `@~/.project-memory/AGENT.md` in `GEMINI.md` | per vendor docs |
| Cursor | the block pasted into User Rules | per vendor docs |
| Anything else | either, in whatever it reads every turn | n/a |

Python 3.9 or newer, which is what a stock macOS ships. The floor is declared in
one place and checked everywhere it matters: `requires-python` stops `pip`, an
exit-69 check in `__main__.py` stops the npm route, which has no package metadata
to refuse anything, and a test asserts that CI actually runs a row on it. Tested
on Ubuntu, macOS and Windows against 3.11 and 3.13, and on 3.9 on Linux and Intel
macOS, on both retrieval paths.

CI also opens the built wheel and asserts the program is inside it. That test
exists because for months it was not: `pyproject.toml` declared `py-modules = []`
and every published distribution contained LICENSE, README, pyproject and ten test
files. Nothing looked, so nobody knew.

## Contributing

```bash
git clone https://github.com/Krowli/project-memory && cd project-memory
pip install -e ".[dev]"
pytest && PROJECT_MEMORY_NO_FTS5=1 pytest && ruff check .
```

Both pytest runs have to pass. The second covers the scan ranker that answers when
SQLite has no FTS5, which every machine in CI does have, so without it that path
rots undetected.

**No proposal lands without a number from `evals/` or a failing test it fixes.**
That rule is why two features that measurably improve retrieval are refused in
this README rather than shipped, and it applies to the maintainer too.

The version is one literal in `src/pagelore/__init__.py`. `npm/package.json`
carries the only copy, because npm cannot read a Python file, and both the packer
and a test refuse a mismatch. To release: bump that literal and the npm one, add a
`CHANGELOG.md` section, then tag.

```bash
git tag -a v0.4.0 -m "pagelore 0.4.0" && git push origin main v0.4.0
```

The tag triggers the release workflow: it checks the tag against the code and the
changelog, opens the wheel, publishes to PyPI through trusted publishing, then to
npm, then cuts the GitHub release with that changelog section as the notes. PyPI
goes first because a PyPI version can never be replaced and an npm one can.
Rehearse the whole path against TestPyPI with a `workflow_dispatch` run first — a
failed publish burns a version number.

## License

MIT — see [LICENSE](LICENSE).
