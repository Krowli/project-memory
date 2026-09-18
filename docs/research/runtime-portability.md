# What agent skills and agent-memory tools actually depend on at runtime

> **Where this lives.** `docs/research/`, one file per question, alongside
> `superpowers-portability.md`. This note was written 2026-09-18 and answers a single
> question: *what runtime does a coding-agent skill or memory tool require of its **user**,
> and how do the ones that work everywhere avoid requiring one?*

**Sources and conventions.**

- `SP` means the installed package
  `/Users/krowli/.claude/plugins/cache/claude-plugins-official/superpowers/6.3.0`. Its non-`.md`
  file tree is byte-for-byte the same set as `main` of https://github.com/obra/superpowers,
  checked with `gh api repos/obra/superpowers/git/trees/main?recursive=1`.
- GitHub facts are cited as `owner/repo path`. Star counts and languages come from
  `gh api repos/<owner>/<repo>` on 2026-09-18 and are the repository's own metadata.
- `[probe]` marks something measured on this machine: macOS, Darwin 23.4.0, Apple silicon,
  stock system paths only (`/usr/bin`, `/bin`), Homebrew paths excluded.
- Vendor docs are cited by URL.
- Where a premise in the brief could not be confirmed from a primary source, it is marked
  **unverified** rather than repeated as fact.

---

## 1. Summary — twelve findings

1. **A superpowers *user* needs no language runtime.** All 14 skills are markdown. The only
   thing that runs on a user's machine by default is one ~50-line bash script fired by the
   Claude Code / Cursor / Copilot `SessionStart` hook, and when bash is missing it exits 0 and
   the plugin keeps working without the injection [`SP/hooks/session-start`;
   `SP/hooks/run-hook.cmd`]. The policy is explicit: "Superpowers is a zero-dependency plugin
   by design" [`SP/AGENTS.md`].
2. **"Zero runtime" is true because superpowers computes almost nothing.** The four skill
   scripts that do real work are bash; the two that need Node (`brainstorming`'s browser
   companion, `writing-skills/render-graphs.js`) are optional extras a user only reaches by
   opting in. There is no search, no index, no ranking anywhere in the package — the thing
   project-memory exists to do is exactly the thing superpowers never does.
3. **The one high-star project that ships real executables cross-platform ships twins:**
   `OthmanAdi/planning-with-files` (26,982 ★, repo language Shell) carries **206 `.sh` and 123
   `.ps1` files** — a PowerShell twin of every POSIX script — plus a Windows-only hook config
   (`.cursor/hooks.windows.json`, which invokes `powershell -ExecutionPolicy Bypass -File …`).
   Its `SKILL.md` tells the model in prose to use "`scripts/resolve-plan-dir.sh` (or `.ps1`)",
   delegating the platform choice to the agent.
4. **That same project treats Python as an optional accelerator with a mandatory fallback.**
   `inject-plan.py` says so in its own docstring: "It is a twin, not a replacement:
   `scripts/inject-plan.sh` stays the reference implementation and the route every host without
   CPython 3 keeps using… Python 3.6 or newer, standard library only. No f-strings and no
   annotations on purpose: an older interpreter must fail at import time with a clean non-zero
   status" — and a non-zero status makes the shell launcher fall back.
5. **There is no single language runtime present by default on macOS *and* Linux *and*
   Windows. None.** POSIX `sh`/`awk`/`perl` cover macOS and Linux and are absent from Windows;
   Windows PowerShell 5.1 is "installed by default on Windows"
   (https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-windows)
   and is absent from stock macOS and Linux; Windows ships **no** Python — `python.exe` there is
   a Store-redirect stub that, "with any command-line arguments will return an error code to
   indicate that Python was not installed"
   (https://learn.microsoft.com/en-us/windows/python/beginners). The only thing guaranteed
   present on all three is the coding agent itself, and no plugin system exposes it as an
   interpreter.
6. **Stock macOS `/usr/bin/sqlite3` already has everything project-memory's index needs.**
   `[probe]` version 3.43.2 (Apple build), `PRAGMA compile_options` lists `ENABLE_FTS5`,
   and `bm25(t, 10.0, 1.0)` with per-column weights, `snippet()`, the `porter` stemmer and
   `unicode61` over Cyrillic all work from the plain CLI. That is the same call shape
   `memory_index.py:301` already makes (`-bm25(pages, 0.0, 5.0, 1.0)`).
7. **But the shell that would drive it is bash 3.2.** `[probe]` `/bin/bash` on stock macOS is
   "GNU bash, version 3.2.57(1)-release" — no associative arrays, no `${var^^}`, no `mapfile`.
   `jq` is **not** present (`/usr/bin/jq` does not exist `[probe]`), and on Debian the `sqlite3`
   CLI is a separate package from `libsqlite3-0`, not part of the base system
   (https://packages.debian.org/stable/sqlite3) — so "sqlite3 is always there" is true for
   macOS, not for Linux.
8. **Ranked full-text search in awk exists, works, and has a measured cost.**
   `andyed/session-cartographer` implements BM25 + reciprocal-rank fusion in
   `plugins/session-cartographer/scripts/bm25-search.awk` (12,373 bytes) driven by
   `scripts/cartographer-search.sh` (**83,108 bytes of bash**), and advertises "Zero
   dependencies (bash + awk)". Its own README states the price: "On a ~122,000-event corpus a
   standard recall returns in tens of milliseconds where the portable search takes ~11
   seconds." Its `docs/SETUP.md` also claims jq "ships with macOS", which is false `[probe]`.
9. **For skills that actually compute, Python is the norm, not the exception.**
   `anthropics/skills` (177,025 ★) contains **70 `.py` files against 2 `.sh` and 1 `.js`**, and
   two `requirements.txt` files. Anthropic's own document skills shell out to `python` and
   `pip install` in their instructions [`anthropics/skills skills/pdf/SKILL.md`]. Nothing in
   that repo ships a compiled binary.
10. **Every agent-memory competitor examined requires a pre-installed runtime, and most
    require *more* than project-memory does.** Basic Memory: Python via `uv`, floor 3.12.
    `tigerless-labs/agent-memory`: Python 3.12 + `uv` + a git checkout + manual `PATH` edit.
    MemoryCustodian: `python3` ≥ 3.10 on `PATH`. mem0: Node 18+ *or* Python 3.10+ **plus an API
    key**, or Docker for self-hosting. Encephalon: Node ≥ 24.15.0. LaPis: Node 20+. The Go ones
    need no runtime but need a binary the user installs by another route.
11. **Nobody solves the binary problem inside the plugin copy step.** Go projects ship
    per-platform release assets and install the *binary* out-of-band —
    `mainline-org/mainline` via `curl -fsSL … install.sh | bash` (which hard-fails on anything
    but Linux/Darwin) with `mainline_0.5.1_{darwin,linux}_{amd64,arm64}` and
    `mainline_0.5.1_windows_amd64.zip` in the release, then installs the *skill* separately with
    `npx --yes skills add …`. `okf-memory/okf-agent-memory` publishes
    `okf-{darwin,linux,windows}-*` plus a Homebrew formula, while its README's quickstart is
    still `make build` (i.e. a Go toolchain).
12. **Download-the-binary-at-first-run does happen, and it happens in prose.** Real SKILL.md
    files instruct the agent to fetch a release and put it on `PATH` —
    `crabwise-ai/crabwalk public/skill.md` (`curl -sL …releases/download/${VERSION}/… | tar -xz
    -C ~/.crabwalk && cp … ~/.local/bin/` plus appending to `~/.bashrc`/`~/.zshrc`),
    `Bitterbot-AI/bitterbot-desktop skills/sherpa-onnx-tts/SKILL.md` (per-platform tarball
    URLs), `LeoYeAI/openclaw-master-skills skills/clawsec-scanner/SKILL.md`. It is a prose
    instruction to the model, never a plugin-system feature.

---

## 2. Competitor table

"Pre-install" means what must already exist on the user's machine before the tool can answer a
single query. "Server?" means a process that must be running.

| Project | ★ | Language | User must pre-install | Server/daemon? | Install mechanism |
|---|---:|---|---|---|---|
| `obra/superpowers` | — | markdown + bash | **nothing** (bash for the hook; Git Bash on Windows, else the hook silently no-ops) | no | plugin/marketplace copy, 12 harnesses |
| `OthmanAdi/planning-with-files` | 26,982 | Shell + PowerShell (+ optional Python) | nothing beyond the platform's own shell | no | Claude Code plugin, `npx skills add`, npm, `pi install`, `hermes`, `dsh` |
| `andyed/session-cartographer` | 7 | bash + awk (+ Node for extras) | bash, awk, **jq** (claimed to ship with macOS; it does not `[probe]`); Node for `/carto`, profile, turbo; Qdrant + llama.cpp for semantic | optional (turbo, Qdrant) | Claude Code / Codex plugin from a release bundle |
| **project-memory** (this repo) | — | Python 3.11+, stdlib only | `python3` ≥ 3.11 | no | plugin copy into 5 harnesses |
| `waittim/MemoryCustodian` | 22 | Python, `dependencies = []`, `requires-python = ">=3.10"` | `python3` ≥ 3.10 on `PATH` | no | Claude Code personal-skills symlink, Codex local marketplace, Gemini skill link, `pip install -e .` |
| `basicmachines-co/basic-memory` | 3,989 | Python 3.12+ | Python via `uv` (`uv tool install basic-memory --prerelease=allow`) | MCP server per client (or paid cloud, $15/mo) | `uv tool install`, or hosted |
| `tigerless-labs/agent-memory` | 940 | Python 3.12+ | Python 3.12 + `uv`; **no PyPI release** — clone + `uv sync --all-packages` + put `.venv/bin` on `PATH` yourself | no (CLI + optional MCP) | `mem setup --host claude-code` writes the host's hooks |
| `mraza007/echovault` | 149 | Python (FTS5 + optional sqlite-vec) | `uv` or `pipx` (installer falls back to a private venv); Windows must use the manual pipx flow | "No background processes, no daemon" — MCP server starts on demand | `curl -LsSf …/install.sh \| sh` (macOS/Linux only) |
| `Coding-Dev-Tools/engraphis` | 175 | Python 3.10+ | `pip install "engraphis[all]"` | yes — dashboard on `127.0.0.1:8700`, MCP server | pip / Docker |
| `mem0ai/mem0` | 65,595 | Python (+ TS SDK) | Node 18+ **or** Python 3.10+, **plus `MEM0_API_KEY`**; self-host needs Docker | yes for anything but the library (cloud platform or `docker compose up`) | `npm i -g @mem0/cli` / `pip install mem0-cli`; ships `.claude-plugin` + `skills/` that document the CLI |
| `isaachinman/encephalon` | 120 | TypeScript, Node ≥ 24.15.0, zero runtime deps | Node ≥ 24.15.0 (uses the built-in `node:sqlite`) | no ("no background daemon or runtime network access") | `npm install --save-dev encephalon && npx encephalon init` |
| `GeneGulanesJr/LaPis` | 46 | JavaScript | Node 20+ and `better-sqlite3` (native module) | MCP server | `pi install git:…`, `npx -y @genegulanesjr/lapis claude-code install` |
| `sverklo/sverklo` | 79 | TypeScript | Node/npm; downloads an ~86 MB ONNX model to `~/.sverklo/models/` on first use | MCP server | `npm install -g sverklo && sverklo init` |
| `okf-memory/okf-agent-memory` | 697 | Go, zero deps | nothing at runtime — but a Go toolchain (`make build`) or a downloaded release binary / Homebrew | embedded MCP server, optional | binary out-of-band; skill lives at `.agents/skills/okf-memory/` |
| `mainline-org/mainline` | 195 | Go | nothing at runtime — the binary is installed separately | no | `curl … install.sh \| bash` (Linux/Darwin only) or `go install`; skill via `npx --yes skills add` |

Also seen in the search but not examined in depth: `Brain0-ai/brain0` (320 ★, Rust),
`Dicklesworthstone/eidetic_engine_cli` (48 ★, Rust), `jayzeng/agentmemory` (22 ★, TS),
`tools-for-agents/cortex` (JS, "FTS5 search… Zero deps"). Their repository descriptions name the
language; their install paths were not read.

---

## 3. obra/superpowers — exactly what executable code it ships

**The complete list of non-markdown, non-manifest files in the package**
(`find SP -type f \( -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.sh' -o -name
'*.mjs' -o -name '*.cjs' \) -not -path '*/tests/*'`, plus `SP/hooks/*`):

| File | Language | Who runs it | Runtime a *user* needs |
|---|---|---|---|
| `hooks/hooks.json`, `hooks/hooks-cursor.json` | JSON | the harness | none |
| `hooks/run-hook.cmd` | cmd/bash polyglot | Claude Code, Cursor, Copilot | on Windows: `cmd.exe` finds Git Bash; if none, **exit 0 silently** |
| `hooks/session-start` | bash (extensionless) | same | bash |
| `scripts/bump-version.sh`, `lint-shell.sh`, `package-codex-plugin.sh`, `sync-to-codex-plugin.sh` | bash | **maintainers only** — release tooling | none for a user |
| `.opencode/plugins/superpowers.js` | JS | OpenCode's own Node process | none extra |
| `.pi/extensions/superpowers.ts` | TS | Pi's own runtime | none extra |
| `.hermes-plugin/__init__.py` | Python | **Hermes's own Python process** | none extra |
| `skills/subagent-driven-development/scripts/{task-brief,sdd-workspace,review-package}` | `#!/usr/bin/env bash` | the agent, inside that skill | bash |
| `skills/systematic-debugging/find-polluter.sh` | bash | the agent | bash |
| `skills/systematic-debugging/condition-based-waiting-example.ts` | TS | nobody — it is a code *example* | none |
| `skills/writing-skills/render-graphs.js` | `#!/usr/bin/env node` | the agent, opt-in | **Node** (+ graphviz) |
| `skills/brainstorming/scripts/{start,stop}-server.sh`, `server.cjs`, `helper.js`, `frame-template.html` | bash + Node | the agent, only after the user accepts the visual companion | **Node** |

**So, plainly: does a user need a runtime installed?**

- **For the skills themselves — no.** All 14 `SKILL.md` files and every reference file are
  markdown. The skill bodies are prose the model reads.
- **For the session-start bootstrap — bash, and it degrades instead of failing.**
  `hooks/hooks.json` declares `"shell": "bash"`; `run-hook.cmd` looks for
  `C:\Program Files\Git\bin\bash.exe`, then `bash` on `PATH`, and its last branch is commented
  "No bash found - exit silently rather than error / (plugin still works, just without
  SessionStart context injection)". `SP/docs/windows/polyglot-hooks.md` explains the choice:
  declaring `"shell": "bash"` "forces the Git Bash route and, when Git Bash is absent, produces
  an actionable 'install Git for Windows' error instead of a shell parser failure."
- **For two optional skill extras — Node.** `brainstorming`'s browser companion runs
  `node server.cjs` (`start-server.sh`), and it is offered only when a question is genuinely
  visual and the user says yes [`SP/skills/brainstorming/SKILL.md` "Visual Companion"];
  `writing-skills/render-graphs.js` is a maintainer-facing SVG renderer.
- **Python appears exactly once, and never on a user's machine as a prerequisite.**
  `.hermes-plugin/__init__.py` is loaded by Hermes, which is itself a Python agent.
- **The policy is written down.** `SP/AGENTS.md`, "Third-party dependencies": "PRs that add
  optional or required dependencies on third-party projects will not be accepted unless they are
  adding support for a new harness… Superpowers is a zero-dependency plugin by design."
  `SP/docs/README.kimi.md` repeats it: "There are no copied skills, symlinks, hooks, or extra
  runtime dependencies."

**The load-bearing caveat.** Superpowers can afford this because it computes nothing. Its
heaviest script, `skills/brainstorming/scripts/start-server.sh`, is process management. There is
no index, no ranking, no query parsing anywhere in the package. It is not evidence that a
searching skill can be runtime-free; it is evidence that a *prose* skill can.

---

## 4. Agent-memory competitors — what the user must have

**`basicmachines-co/basic-memory`** (3,989 ★, Python). README badge: "Python 3.12+". The local
route is "**Requires Python via [`uv`](https://docs.astral.sh/uv/)**" and
`uv tool install basic-memory --prerelease=allow` — the flag is mandatory because 0.23 depends on
a FastMCP 4 pre-release. It is MCP-native: each client speaks to a `basic-memory` MCP server.
The README's first section is a paid cloud alternative whose selling point is the install it
replaces: "Claude, Codex, or Cursor connected in 30 seconds. **No Python, no JSON, no
terminal.** $15.00/mo locked in for life."

**`mem0ai/mem0`** (65,595 ★, Python). Three tiers in its own table: Library
(`pip install mem0ai`), Self-Hosted Server (`docker compose up`), Cloud Platform. Its skill
declares the requirement in frontmatter — `compatibility: Node.js 18+ (npm install -g @mem0/cli)
or Python 3.10+ (pip install mem0-cli), MEM0_API_KEY env var`
[`mem0ai/mem0 skills/mem0-cli/SKILL.md`]. mem0 does ship `.claude-plugin/`, `.codex-plugin/`,
`.kimi-plugin/` and a `skills/` tree, but those skills *document a CLI the user installs
separately*; the plugin copies no executable of its own.

**`tigerless-labs/agent-memory`** (940 ★, Python) — the closest architectural twin to
project-memory: "plain Markdown as the source of truth, local ranked retrieval… the SQLite index
beside them is a cache you can delete at any time". Its install is the heaviest of the lot:
"Requires Python 3.12 or higher and uv. There is no release on PyPI yet, so install from a
checkout" → `git clone` + `uv sync --all-packages`, then the user must
`export PATH="$PWD/.venv/bin:$PATH"` because "the hook installed in the next section is a bare
`mem-hook` command, and a host that cannot resolve it records nothing."

**`waittim/MemoryCustodian`** (22 ★, Python) — the closest *packaging* twin. `pyproject.toml`:
`requires-python = ">=3.10"`, `dependencies = []`. It ships `bin/memory-custodian`, a bash stub
that execs `scripts/memory-custodian`, which is POSIX `sh`:

```sh
python_bin=${PYTHON:-python3}
PYTHONPATH="$plugin_root/cli${PYTHONPATH:+:$PYTHONPATH}" exec "$python_bin" -m memory_custodian.main "$@"
```

That is the whole strategy: take `python3` from `PATH`, allow `$PYTHON` to override, vendor the
package under `cli/` so nothing is installed. Its `skills/memory-custodian/SKILL.md` never
mentions Python at all. It has the same stock-macOS problem project-memory has, one minor
version lower, and has not solved it.

**`mraza007/echovault`** (149 ★, Python). `curl -LsSf …/install.sh | sh`; "The curl installer
supports macOS and Linux. Windows users can use the manual `pipx` flow below." "The installer
uses `uv` or `pipx` when either is available. Otherwise it creates a dedicated virtual
environment under `~/.local/share/echovault` — it never modifies the system Python." Storage is
Markdown + "SQLite: FTS5 + sqlite-vec"; "Zero idle cost — No background processes, no daemon…
The MCP server only runs when the agent starts it."

**`isaachinman/encephalon`** (120 ★, TypeScript). "Use Node.js **24.15.0 or later** on Linux,
macOS or Windows… The installed package has zero runtime dependencies, no installation lifecycle
scripts and no Bun requirement." `package.json`: `"engines": {"node": ">=24.15.0"}`. The index is
SQLite with no native module because Node 24 has one built in — the repo's own design note says
"**Tech stack:** TypeScript 7, Node.js 24.15+ built-in `node:sqlite`"
[`isaachinman/encephalon encephalon/_artifacts/context/…/plans/2026-08-17-sqlite-schema-semantics.md`].
This is the only stack found where SQLite arrives *with* the runtime rather than beside it.
Install is `npm install --save-dev encephalon && npx --no-install encephalon init`, and `init`
"adds a reversible managed block to root `AGENTS.md` and `CLAUDE.md`" pointing at the skill.

**`Coding-Dev-Tools/engraphis`** (175 ★, Python 3.10+) — `pip install "engraphis[all]"`, a
dashboard at `127.0.0.1:8700`, an MCP server, Docker compose, and a `scripts/launch_dashboard.ps1`
"Windows convenience wrapper". A server-shaped product, not a skill.

**`GeneGulanesJr/LaPis`** (46 ★, JS) — "Requirements: Node.js 20+, `better-sqlite3` for local
SQLite access, No Python dependency". `better-sqlite3` is a native module, i.e. a compile or a
prebuilt download at npm-install time. Claude Code install is
`npx -y @genegulanesjr/lapis claude-code install`, which writes `.mcp.json` and
`.claude/settings.json`.

**`sverklo/sverklo`** (79 ★, TS) — `npm install -g sverklo && sverklo init`; MCP for Claude Code,
Cursor, Windsurf, Codex; "The bundled embedding model (`all-MiniLM-L6-v2` ONNX, ~86 MB) is
downloaded from HuggingFace on first use into `~/.sverklo/models/`."

**The Go pair.** `okf-memory/okf-agent-memory` (697 ★) markets exactly the runtime argument —
its benchmark table row "Process Cold-Start Overhead" reads "250ms – 600ms (Python VM boot) |
80ms – 180ms (V8 / Deno boot) | **< 4 ms (Compiled Single Binary)**". Its skill
(`.agents/skills/okf-memory/SKILL.md`) is pure markdown that calls `okf search … --json` as the
"Fallback: Deterministic CLI" behind MCP tools. `mainline-org/mainline` (195 ★) is the same
shape: `skills/mainline/SKILL.md` is the *only* skill file in the repo, and the binary is
installed by a separate command.

---

## 5. How widely-installed Claude Code plugins and skills ship executable code

**`anthropics/skills`** (177,025 ★) — the official example set, installed via
`/plugin marketplace add anthropics/skills`. File census of the whole tree, excluding `.md`,
fonts and licences:

| Extension | Count |
|---|---:|
| `.xsd` (OOXML schemas, data) | 117 |
| `.py` | 70 |
| `.xml` | 6 |
| `.html` | 3 |
| `.sh` | 2 |
| `.js` | 1 |

Plus `skills/mcp-builder/scripts/requirements.txt` and `skills/slack-gif-creator/requirements.txt`.
No compiled binaries. The document skills (`docx`, `pdf`, `pptx`, `xlsx`) — the ones that power
Claude's real file capabilities — are Python, and their instructions call `pip` inline:
"`# Requires: pip install pytesseract pdf2image`" [`anthropics/skills skills/pdf/SKILL.md:235`].

**The official marketplace plugins installed on this machine** `[probe]`, at
`~/.claude/plugins/cache/claude-plugins-official/`:

| Plugin | What it ships | Runtime the user needs |
|---|---|---|
| `code-review`, `frontend-design` | `commands/*.md`, `README.md`, `LICENSE` — nothing else | none |
| `context7` | one `.mcp.json`, `"type": "http"` to `https://mcp.context7.com/mcp` | none — its own manifest says "no local Node.js or npx required" |
| `playwright` | one `.mcp.json`: `{"command": "npx", "args": ["@playwright/mcp@latest"]}` | **Node/npx** |
| `superpowers` | see §3 | bash (degrading) |
| `vercel` | markdown skills + `.mcp.json` + `bun.lock`/`bunfig.toml` and a TS test suite | none for a user; Bun for contributors |
| `claude-hud` (third-party) | prebuilt `dist/*.js` **plus a vendored `node_modules/` (49 entries)** | **Node 18+ or Bun**; on Windows its README says "Node.js LTS is the supported runtime… `winget install OpenJS.NodeJS.LTS`" |

**Curated marketplaces.** `trailofbits/skills-curated` (505 ★): its executables are
`plugins/ghidra-headless/skills/…/scripts/*.sh` + Java scripts for Ghidra, and
`plugins/last30days/scripts/*.py` — bash and Python. `fivetaku/gptaku_plugins` (1,147 ★): 28
`.py`, 2 `.sh`, 1 `.cjs`. `Piebald-AI/claude-code-lsps` (520 ★) ships **only JSON**
(`.lsp.json` + `plugin.json`) and pushes every dependency onto the user: "You need to install
various components in order for the plugins to use them… `rustup component add rust-analyzer`."

**Categories, ranked by how common they are for anything that computes:**

1. **Python script invoked from SKILL.md prose** — dominant. Anthropic's own skills, Trail of
   Bits, gptaku.
2. **Bash script** — second, and the default when the job is process/file wrangling
   (superpowers, ghidra-headless, planning-with-files).
3. **Node** — used when the skill needs a server, a browser, or a rendering library
   (`playwright` via npx, `claude-hud`, superpowers' brainstorm server).
4. **Pure markdown / MCP manifest** — very common, but it delegates the computation to a remote
   server (`context7`) or to the model.
5. **Compiled binary shipped by the plugin copy** — **found in zero of the plugins examined.**
   Binaries are always installed by a separate command (§7).

---

## 6. The shell option, honestly assessed

**What is actually on a stock machine.**

`[probe]` macOS, Darwin 23.4.0, system paths only:

| Tool | Present | Note |
|---|---|---|
| `/bin/sh`, `/bin/bash`, `/bin/zsh`, `/bin/csh`, `/bin/dash`, `/bin/ksh` | yes | `bash --version` → **3.2.57(1)-release**, 2007 vintage |
| `/usr/bin/awk` | yes | `awk version 20200816` (BWK awk, not gawk) |
| `/usr/bin/perl` | yes | v5.34.1 |
| `/usr/bin/sqlite3` | yes | 3.43.2; `ENABLE_FTS5` present |
| `/usr/bin/python3` | yes | **3.9.6** — below project-memory's 3.11 floor |
| `/usr/bin/ruby`, `/usr/bin/tclsh`, `/usr/bin/osascript`, `/usr/bin/curl` | yes | |
| `jq` | **no** | `/usr/bin/jq` does not exist |
| `node` | **no** | |

**What stock macOS `sqlite3` can already do** `[probe]`, all from the plain CLI:

```
$ /usr/bin/sqlite3 :memory: "CREATE VIRTUAL TABLE t USING fts5(a,b);
    INSERT INTO t VALUES('alpha beta','gamma');
    SELECT bm25(t, 10.0, 1.0) FROM t WHERE t MATCH 'alpha';"
-1.96428571428571e-06
```

`snippet()` works, the `porter` stemmer works, `unicode61` tokenises Cyrillic. In other words the
BM25F core of `memory_search.py` — `-bm25(pages, 0.0, 5.0, 1.0)` at
`skills/project-memory/scripts/memory_index.py:301` — is expressible as a single SQL statement
against a binary Apple already ships.

**What that does not buy.** The `sqlite3` CLI is not guaranteed on Linux: on Debian stable it is
a standalone package that depends on `libsqlite3-0`, not part of the base system
(https://packages.debian.org/stable/sqlite3). And it does not exist on stock Windows — a claim
this research **could not confirm from a Microsoft primary source**; it is the brief's premise,
consistent with the fact that every plugin surveyed routes Windows through PowerShell or Git
Bash and never through a preinstalled POSIX tool.

**Ranked search in awk: one real, working example.** `andyed/session-cartographer` (7 ★,
"Map and search Claude Code & ChatGPT session history. BM25, semantic search and rank fusion via
awk"):

- `plugins/session-cartographer/scripts/bm25-search.awk` — 12,373 bytes. `BEGIN { k1 = 1.2;
  b = 0.75; … }`, a two-pass design where "pass 1 owns ndocs, avgdl and df", hand-written JSON
  field extraction (`extract()`, `extract_num()`), and a hand-written ISO-8601-to-epoch parser
  because awk has no date library — with a comment that it must stay "byte-for-byte the same
  arithmetic as `ts_to_epoch()` in `cartographer-search.sh:rank_fuse`".
- `plugins/session-cartographer/scripts/cartographer-search.sh` — **83,108 bytes** of bash
  around it.
- README: "`/remember` … Runs BM25 + RRF search across event logs and transcripts. **Zero
  dependencies (bash + awk).**"
- And the measured cost, from the same README: "On a ~122,000-event corpus a standard recall
  returns in tens of milliseconds where the portable search takes ~11 seconds; the daily
  cross-project pulse went from 12.4 s to 1.9 s end to end." The fast path is a Node service
  (`scripts/cartographer-turbo.js`) that is off by default.
- It has no `.ps1` files and no Windows story.
- Its `docs/SETUP.md` claims the minimum is "zero dependencies beyond bash + jq (ships with
  macOS)" — jq does not ship with macOS `[probe]`. A shell tool acquires dependencies without
  anyone noticing.

**The only project found that is genuinely cross-platform without a runtime.**
`OthmanAdi/planning-with-files` (26,982 ★), and its method is duplication:

- 206 `.sh` + 123 `.ps1` + 141 `.py` in the tree; the shipped skill directory
  (`skills/planning-with-files/scripts/`) carries `.sh` and `.ps1` side by side —
  `attest-plan`, `check-complete`, `init-session`, `ledger-append`, `ledger-summary`,
  `phase-status`, `resolve-plan-dir`, `set-active-plan`.
- Per-platform hook manifests: `.cursor/hooks.json` and `.cursor/hooks.windows.json`, the latter
  invoking `powershell -ExecutionPolicy Bypass -File .cursor/hooks/…ps1`.
- The dispatch decision is made **by the model, from prose**: "Use the installed
  `scripts/resolve-plan-dir.sh` (or `.ps1`)…", and "run `sh "<skill-dir>/scripts/set-active-plan.sh"
  --list` or, in Windows PowerShell, `& "<skill-dir>/scripts/set-active-plan.ps1" -List`"
  [`skills/planning-with-files/SKILL.md`].
- Python is present but demoted. `inject-plan.py` exists only because forking is slow under Git
  Bash: "One UserPromptSubmit fire forks about 130 times… Under Git Bash on Windows a fork costs
  about 90 ms, so the same fire took seven to twelve seconds against the 10 s hook timeout".
  Its contract: "Exit status: 0 means 'ran'… Any other status means 'could not run'; the shell
  launcher falls back to the reference chain", and a parity test
  (`tests/test_inject_plan_python_parity.py`) "runs both over the same fixtures and asserts
  byte-identical stdout".

**Is there a single runtime present by default on macOS + Linux + Windows?**

**No.** Coverage by candidate:

| Candidate | macOS | Linux | Windows |
|---|---|---|---|
| POSIX `sh` / `awk` / `perl` | yes | yes (perl not on minimal images) | **no** |
| Windows PowerShell 5.1 | no | no | **yes** (MS docs, above) |
| Python | yes, **3.9.6** | usually, version varies | **no** (Store stub errors out) |
| `sqlite3` CLI | yes | separate package | no (unverified) |
| Node | no | no | no |
| .NET / `dotnet` | no | no | shipped with Windows components, not a scripting entry point |

The only thing guaranteed on all three platforms is the coding agent's own process, and no
plugin system — Claude Code, Codex, Cursor, Gemini, Kimi — exposes it as an interpreter. The
industry's answer, where anyone has answered at all, is two implementations (bash + PowerShell)
with the model choosing between them.

---

## 7. The compiled-binary option

**Nobody gets a binary in through the plugin copy.** Across every plugin examined — the official
marketplace, Trail of Bits, gptaku, Piebald, the memory tools — **not one** ships a compiled
executable inside the copied plugin directory. The three routes actually used:

**(a) Out-of-band installer, binary from GitHub releases.** `mainline-org/mainline`:

```bash
curl -fsSL https://raw.githubusercontent.com/mainline-org/mainline/main/install.sh | bash
mainline version
```

The script detects OS and arch and refuses anything else — `detect_os()` handles only `Linux`
and `Darwin`, `detect_arch()` only `amd64`/`arm64`; it verifies a SHA-256 using `sha256sum` or
`shasum`, and installs into the first writable directory among `/usr/local/bin`,
`/opt/homebrew/bin`, else `$HOME/.local/bin`. Release `v0.5.1` carries
`mainline_0.5.1_darwin_{amd64,arm64}.tar.gz`, `mainline_0.5.1_linux_{amd64,arm64}.tar.gz`,
`mainline_0.5.1_windows_amd64.zip` and `checksums.txt` — so a Windows binary exists but the
installer will not install it. The **skill** is then installed by a completely separate command:
`npx --yes skills add mainline-org/mainline --skill mainline --agent codex claude-code cursor pi
--global --yes`.

**(b) Release binaries + package manager, skill committed to the repo.**
`okf-memory/okf-agent-memory` release `v0.4.1`:
`okf-darwin-{amd64,arm64}`, `okf-linux-{amd64,arm64}`, `okf-windows-{amd64,arm64}.exe`,
`okf-starter-pack-v0.4.1.{tar.gz,zip}`, `okf.rb` (a Homebrew formula), `checksums.txt`. The skill
is plain markdown committed at `.agents/skills/okf-memory/SKILL.md` and simply assumes `okf` is
callable. The README's quickstart is still `make build` — i.e. the documented path requires a Go
toolchain even though prebuilt binaries exist.

**(c) Download at first run, instructed in the skill's own prose.** Found by code-searching
SKILL.md files for `releases/download`:

- `crabwise-ai/crabwalk public/skill.md` — a single line that resolves the latest tag through
  the GitHub API, untars into `~/.crabwalk`, copies the binary to `~/.local/bin`, `chmod +x`, and
  appends a `PATH` export to `~/.bashrc` and `~/.zshrc`.
- `Bitterbot-AI/bitterbot-desktop skills/sherpa-onnx-tts/SKILL.md` and
  `understudy-ai/understudy skills/sherpa-onnx-tts/SKILL.md` — a JSON table of per-platform
  release tarballs (`…-osx-universal2-shared.tar.bz2`, `…-linux-x64-shared.tar.bz2`).
- `LeoYeAI/openclaw-master-skills skills/clawsec-scanner/SKILL.md` — a versioned release base URL;
  its `lost-bitcoin` skill tells Windows users to download and run a zipped executable.

This is the pattern the brief asked about, and it is worth naming what it is: not a plugin
feature, but an instruction to a language model to run `curl … | tar` and edit the user's shell
profile. No integrity check appears in the crabwalk one-liner beyond what GitHub provides.

**Adjacent evidence: vendoring instead of compiling.** `claude-hud` `[probe]` commits both
`dist/` (compiled TS) and a 49-entry `node_modules/` into the plugin, which is the closest
anything comes to "ship the dependency in the copy" — and it still requires Node on `PATH`.
`GeneGulanesJr/LaPis` needs `better-sqlite3`, a native module, and therefore an npm install that
compiles or downloads a prebuilt `.node`.

---

## 8. What this means for project-memory

The repository today is Python 3.11+, stdlib only, ~1,865 lines across five scripts
(`memory_index.py` 323, `memory_lib.py` 479, `memory_search.py` 478, `memory_stats.py` 135,
`memory_write.py` 450), with the ranking already delegated to SQLite
(`CREATE VIRTUAL TABLE pages USING fts5(…)`, `-bm25(pages, 0.0, 5.0, 1.0)`). `install.sh:77`
probes candidates for `>= (3, 11)` and hard-fails otherwise.

The options the evidence supports, with their real costs:

**A. Keep Python, lower the floor.** A grep of the five scripts for the usual 3.11-only
constructs (`tomllib`, `datetime.UTC`, `ExceptionGroup`, `StrEnum`, `except*`) finds none, and
all five already carry `from __future__ import annotations`. Cost: whatever an actual 3.9 test
run turns up (not performed here), plus permanently testing against an interpreter Apple ships
but does not update. Gain: works on stock macOS. **Does nothing for Windows** — there is no
Python there at any version. Precedent: MemoryCustodian sits at 3.10 and has the same hole;
Basic Memory and tigerless-labs went the *other* way, to 3.12 + `uv`, and simply require the user
to install a runtime.

**B. Ship a PowerShell twin of every script.** This is the only approach in the survey that
genuinely reaches all three platforms with no user install:
`planning-with-files`, 26,982 ★, 206 `.sh` + 123 `.ps1`, with the model picking from prose in
`SKILL.md`. Cost: two implementations of BM25F, the index, the writer and the validator, kept in
step — and that project pays for the risk with a byte-for-byte parity test between its twins.
For 1,865 lines of Python that is a large, permanent duplication.

**C. Rewrite in POSIX shell + `/usr/bin/sqlite3`.** The ranking itself is free: stock macOS
sqlite3 3.43.2 has FTS5, `bm25()` with column weights, `snippet()` and the porter stemmer
`[probe]`. What is not free: the target shell is bash 3.2 (2007); `jq` is absent, so JSON and
frontmatter parsing is hand-rolled; the `sqlite3` CLI is a separate package on Debian; and
Windows is not covered at all. The one honest cost estimate available is
`andyed/session-cartographer`: 83,108 bytes of bash + 12,373 bytes of awk for BM25 + RRF, ~11 s
on a 122,000-document corpus, a Node fast-path bolted on to fix that, and a `SETUP.md` that
already mis-states its own dependencies.

**D. Rewrite in awk.** A working precedent exists (`bm25-search.awk`, k1=1.2, b=0.75, two-pass
df/avgdl) but it is 12 KB of awk that hand-parses JSON and hand-computes epoch seconds, and it
still needs a bash driver an order of magnitude larger. Same Windows hole as C.

**E. Compile a binary (Go/Rust).** Removes the runtime question entirely at run time — `okf`
markets "< 4 ms (Compiled Single Binary)" against "250ms – 600ms (Python VM boot)" — but moves
the whole problem into distribution, and **no plugin system in the survey can install a binary**.
The three real routes are all a second install step the user performs: `curl … | bash`
(mainline — Linux/Darwin only, despite shipping a Windows zip), Homebrew/releases (okf), or a
SKILL.md instruction to download and `chmod +x` at first run (crabwalk, sherpa-onnx-tts). Every
one of them breaks the property project-memory currently has: the plugin copy is the whole
install.

**F. Node ≥ 24.** The single stack found where SQLite arrives with the runtime and needs no
native module: `isaachinman/encephalon`, "zero runtime dependencies", `node:sqlite`, `engines:
node >= 24.15.0`. It replaces "user must have Python 3.11" with "user must have Node 24.15",
which is a *newer* requirement than the one being escaped, and is not preinstalled anywhere.

**What the survey does not support.** That a runtime-free implementation is normal: it is not.
Superpowers is runtime-free because it computes nothing (§3); every tool in §4 that actually
ranks anything demands a runtime, a binary, a server, or an API key. And that Python is an
unusual choice: it is the most common language in the ecosystem for skills that compute
(`anthropics/skills`: 70 `.py` vs 2 `.sh` vs 1 `.js`), with the floor typically set at 3.10–3.12
— i.e. above stock macOS, exactly where project-memory already sits.
