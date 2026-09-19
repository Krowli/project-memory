# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`evals/mcp_probe.py`**, a stdio MCP server exposing the two tools, and
  `evals/acceptance.py --pointer mcp|mcp+include` to run a real session against
  it. The CLI was chosen early and never measured against MCP; this settles it
  with numbers rather than opinion. Retrieval quality was never the question —
  the server calls the same functions — so what was measured is whether an agent
  reaches for the memory more reliably when the tools are in its tool list.
  Fifteen sessions per arm: the instruction line 15/15, MCP on Claude Code's
  default settings **0/15**, MCP with `ENABLE_TOOL_SEARCH=false` 15/15, both
  together 15/15. The zero is Claude Code deferring MCP tools behind tool search
  by default, so the single advantage MCP was supposed to have is absent out of
  the box. MCP is not shipped; the probe stays so the question can be re-run.

## [0.3.4] - 2026-09-19

### Added

- **The install asks which agents should use it, and writes the line itself.**
  Printing instructions and leaving the user to carry them out was the step
  people finished the install without taking. It now lists Claude Code, Gemini
  and Codex with the file each one reads, shows the exact path and the exact
  line before touching anything, and writes only after a confirmation. What it
  writes is fenced by marker comments: a second install replaces that block
  rather than stacking another copy, `--uninstall` takes it back out, and
  everything the user wrote around it survives. Declining prints the line to
  add by hand, which is what it used to do unconditionally.

### Fixed

- **The "install here or everywhere" question could not change anything.** It
  ran after the destination had already been worked out, so both answers led to
  the same directory. It now runs before, and a pty-driven test asserts that
  answering "only this one" puts the skill in the repository and not in the
  home directory — the questions are interactive, so a test that pipes stdin
  proves nothing about them.

## [0.3.3] - 2026-09-19

### Added

- **The install ends by naming the line that makes it work.** It printed where
  the files went and stopped, so someone who ran one command was finished and
  had no way to know they were not: the scripts sit on disk and the agent never
  reaches for them until the instruction block is in its configuration. The
  final message now gives that line with the path filled in for the install it
  just did, the file to put it in for each agent, and the command that undoes
  the whole thing.
- **It asks whether to install for every project or only for this one**, when
  there is a terminal to answer on and a repository under foot for the second
  option to mean anything. Before, standing inside a project and running it with
  no flags installed globally in silence, which reads as a script with no
  opinion rather than one that made a choice. Piped through CI it stays global
  without stalling.

## [0.3.2] - 2026-09-19

### Added

- **`./install.sh --uninstall`.** There was no way to take the skill off a
  machine, so the only instruction anyone could be given was a pair of
  `rm -rf` typed by hand, next to a directory of the user's own pages. It
  removes the skill directory and the symlink the install made, names every
  path it deletes, and leaves three things while saying so: the `.memory/`
  stores in your projects, the line you added to your agent's instruction file,
  and any agent definition you wrote. A symlink is removed only when it
  resolves to the directory being deleted, so a link of yours pointing
  elsewhere survives. It runs before the git and Python checks, because taking
  a program off a machine must not depend on the toolchain that put it there.
  README documents it.

## [0.3.1] - 2026-09-19

### Changed

- **README documents how an update actually reaches a user**, per install path,
  because it does not reach them by itself: Claude Code leaves auto-update off
  by default for third-party marketplaces, and a `curl` install has no update
  channel at all beyond `./install.sh --check`. Everything in 0.3.0 that came
  after the tag — the shipped instruction block and the 3.9 floor — was
  unreachable for anyone who had already installed, because a user only
  receives an update when the manifest version changes. Hence this release.

- **The Python floor drops from 3.11 to 3.9**, which is what a stock macOS
  already ships — until now `install.sh` refused the interpreter at
  `/usr/bin/python3`, so the skill would not run on a Mac without a Python
  installed first. The floor was never earned: the five scripts carry no 3.10 or
  3.11 construct, all of them already use `from __future__ import annotations`,
  and the whole suite passes under 3.9.6. CI now runs 3.9 on Linux and Intel
  macOS alongside 3.11 and 3.13 (GitHub publishes no 3.9 build for arm64 macOS
  or Windows), and a test fails if the four places that declare the floor drift
  apart. Windows, which ships no Python at all, stays a documented prerequisite.
- README rewritten around the three questions people ask first: is the skill
  global or local (global by default, the store is always per project), how to
  make an agent keep the memory without hooks (one paste into the agent's
  global instruction file, paths per vendor docs), and what was measured, with
  every table and the command that reproduces it.
- The calibration medians quoted in `SKILL.md` and `references/retrieval.md`
  (5.32 against 5.29) predated the FTS5 index; re-measured with the current
  harness they are 9.93 against 8.73. The conclusion is unchanged: a score
  threshold cannot tell an answerable question from an unanswerable one.

## [0.3.0] - 2026-09-16

### Added

- **`memory_search.py --touching PATH`** — the pages whose `sources` cite that
  file, or anything under that directory, come first, marked `▸ touches <path>`,
  with or without query words. `sources` was the one field every page must carry
  and the one field ranking never read. Measured on a new 50-query `touching`
  set in `evals/corpus.json`: typing the path as words puts the right page first
  38% of the time (nDCG@10 0.545); the flag puts it first by construction
  (0.986, paired +0.441 [+0.349, +0.539]). Without the flag nothing changes,
  and the existing tables did not move. Sources are not in the index, so a
  `--touching` search reads every page.
- **The write gate runs on read.** A page that arrived around `memory_write.py`
  and is under 200 characters is not ranked; search names it on stderr and in
  `--json` so it can be rewritten through the script. A page with no sources is
  shown, marked `⚠ no sources`. `MIN_BODY` moved to `memory_lib` so writer and
  reader share one floor. Search runs on every agent the skill is installed in,
  which is what makes it the place for the check.
- Every log line carries the session id Claude Code exports to the Bash tool
  (`CLAUDE_CODE_SESSION_ID`), and `memory_stats.py` reports sessions, sessions
  that searched and never wrote, and writes per session — the write side's
  "did it happen", collected by the scripts themselves.
- `evals/acceptance.py`: a real session of the agent you name, a question only
  the store answers, and a check of the store's log for the search. The only
  proof that an agent uses the memory unprompted; run it per harness.
- `docs/research/`: primary-source notes behind decisions, starting with how
  superpowers stays portable across thirteen harnesses.

### Removed

- **The three Claude Code hooks.** SessionStart announced the memory,
  PreToolUse denied a hand-written page, Stop reminded a session that changed
  files and wrote nothing — and every one existed on one harness while the
  skill claims to work on any. `hooks/` is gone, `install.sh` no longer writes
  `settings.json` (`--no-hook` with it), and the Cursor manifest declares no
  hooks. Announcing the memory is the skill `description`, the context files
  and the `AGENTS.md` snippet, the way superpowers runs on Codex, Devin and
  Grok; the gate moved to read; the reminder became a finishing rule in
  `SKILL.md` and the pointer files. See `.memory/scripts-carry-the-contract-not-hooks.md`.

### Changed

- `evals/dense_probe.py --static MODEL` runs the hybrid over a model2vec static
  embedding model and reports the cold process cost next to the shipped search.
  Measured with three `potion` models: no hybrid gain clears zero, and the
  cheapest cold start is 527 ms against 86 ms for the whole shipped search — the
  cheap form of the embedding idea is refused on the same grounds as the
  expensive one. See `references/retrieval.md`.

## [0.2.2] - 2026-08-18

### Fixed

- **The hooks were registered as `python3`, which is not a command Windows has.**
  Its installer puts `python`, `py` and `pymanager` on PATH; `python3` exists only
  as an optional versioned alias. So on Windows both hooks silently never ran —
  the agent was never told it had a memory, and the write guard blocked nothing,
  which is precisely the hole it exists to close. `install.sh` now resolves a
  working interpreter (`python3`, then `python`, then `py -3`, each checked for
  3.11+) and writes that one into `settings.json`; `--interpreter` forces a
  choice. It also no longer accepts a Python below 3.11, which the old existence
  check did — on macOS that is `/usr/bin/python3`, still 3.9.
- **The suite could not have caught it.** Every hook test invoked `sys.executable`
  and never the string the installer writes, and `actions/setup-python` puts a
  `python3` shim on Windows runners, so both layers hid it. A test now takes the
  command out of the generated `settings.json` and runs it through a shell.
- `hooks/hooks.json` cannot branch per platform, so the plugin path still
  hard-codes `python3`. That limitation is now in the README rather than in a
  surprise, with a test that keeps the two in sync.

## [0.2.1] - 2026-08-18

### Fixed

- **Contended writes terminated a sibling writer on Windows.** The lock decides
  staleness by asking whether the owning process still exists, and used
  `os.kill(pid, 0)` to ask. That is a liveness probe on POSIX and a kill on
  Windows, where every signal but CTRL_C and CTRL_BREAK is delivered by calling
  TerminateProcess. CI caught it as a hung test run, which was the mild version of
  the symptom. Liveness now goes through a platform check — `OpenProcess` on
  Windows, distinguishing "no such process" from "access denied" — and falls back
  to the mtime rule wherever the answer is unknowable. A test pins `os.kill` to
  that one guarded probe.
- The host identity in a lock file came from `os.uname()`, which does not exist on
  Windows, so every lock there was written and compared as `unknown-host`.
- **A concurrent search made a write fail outright on Windows.** `os.replace`
  replaces a file regardless of who has it open on POSIX and refuses with
  WinError 5 while any reader holds a handle — and a search reading the store is
  exactly that reader. The replace now retries for a few seconds instead of
  raising.
- **A process that had exited was reported as running on Windows.** `OpenProcess`
  succeeds for as long as anyone holds a handle to a dead process, so the handle
  alone means nothing; the exit code decides, with 259 (`STILL_ACTIVE`) meaning
  running.
- **17 of 200 concurrent log lines went missing on Windows.** One `O_APPEND` write
  is atomic against other processes on POSIX and is not on Windows; appends within
  a process are now serialised.
- Tests that depend on POSIX file modes, `mkfifo` or `geteuid` are skipped on
  Windows rather than faked, so the Windows run reports what it actually covered.

## [0.2.0] - 2026-08-18

An audit of the skill against its own claims. Four ways a re-run could destroy
part of a page, a store that could take retrieval down or leak a file it never
owned, a write gate with an unguarded side door, and a contract naming a script
path that existed in one install mode out of four.

### Fixed

- **Re-running a write no longer loses content.** `## ` lines inside a code fence
  are content, not headings — the previous splitter deleted the closing fence and
  everything after it. A body with no heading at all used to be dropped whenever
  the page already had lead-in prose. Sections are replaced in place instead of
  moving to the end of the file, so a one-section amendment reads as one in
  `git diff`. Each of these exited 0 and logged a successful write.
- **Frontmatter fields the tooling does not own are preserved.** Rebuilding from a
  fixed whitelist silently deleted anything else the page carried, which blocked
  extending the format at all.
- **The 200-character floor applies to the resulting page, not to the increment.**
  Recording "this was reversed in June, here is why" against an existing page was
  refused — the cheapest and most valuable write in the system.
- **Concurrent writes to one slug no longer lose sections.** An advisory per-page
  lock plus `os.replace`; measured before the fix, twelve to twenty parallel
  writers lost up to 16 of 20 sections, all exiting 0. A reader can no longer
  observe a half-written page, and log lines cannot interleave.
- **One undecodable page no longer kills every search in the project.** Pages are
  read with `errors="replace"`.
- **NFD text is findable.** `\w+` does not match combining marks, so the NFD form
  of `ёлка` tokenised as `['е', 'лка']` and recall across an NFC/NFD boundary was
  zero — on macOS, which produces that form. Text is normalised to NFC and folded
  with `casefold()`, which also covers `STRASSE` / `straße`.
- **A search no longer creates a store or edits `.gitignore`.** Logging a miss used
  to dirty the working tree of a repository that never opted in. The write path
  still creates and shields the store it needs, including on a refusal.
- **A page symlinked outside the store is ignored.** `ln -s ../.env
  .memory/env-notes.md` made an ordinary search rank and print a secret.
- **Only top-level `*.md` files are indexed.** `mkdir archive; mv` used to leave the
  page indexed and return two hits with the same slug.
- **A store that is a dangling symlink is refused with a `FIX:` line** instead of a
  raw `FileExistsError` — the shape `install.sh --store home` produces if its
  target is gone.
- `memory_stats.py` reports a real median for even counts and tolerates a log line
  from another writer.
- **Every command in `CLAUDE.md`, `AGENTS.md` and `GEMINI.md` now runs.** All three
  hard-coded `.agents/skills/…`, which exists only after `install.sh --project` —
  not in a clone, which is the case `CLAUDE.md` says it exists for. A test extracts
  every command from those files and checks it.
- `install.sh --help` no longer truncates mid-table, hiding two store modes.
- A missing `--kind` is logged as `no_kind` rather than sharing `bad_kind` with an
  invalid one; the two call for opposite fixes.

### Added

- **The runtime knows its own version.** `--version` on every script, and the
  session hook tells the agent which version the project is running. A `curl`
  install has no package manager to ask, so until now neither the user nor the
  agent could tell 0.1.0 from 0.2.0 on disk.
- **`install.sh` installs the latest released tag**, not the tip of `main`, so an
  install is reproducible and a version number means something.
  `PROJECT_MEMORY_REF` still takes a branch or a specific tag, and
  `install.sh --check` reports what is installed against what is released without
  installing anything. A test now guards the `--help` line range, which had
  silently truncated once already.

- **A reproducible evaluation, in the repository.** `python3 evals/run.py --by-type`
  over 90 pages and 270 queries with paired bootstrap intervals, plus an ambiguous
  set and an unanswerable set. `evals/gate_value.py` measures what the write gate
  is worth by putting the stubs it refuses back into the corpus. Nothing in
  `references/retrieval.md` is now argued from figures a reader cannot re-run.
- **A persistent SQLite FTS5 index** (`memory_index.py`), and it is a cache the
  search is allowed to ignore. End to end, as a shell invocation: 235 ms → 99 ms at
  90 pages, 1887 ms → 174 ms at 1000, 4637 ms → 196 ms at 5000. The ~5000-page
  ceiling the documentation used to name is gone. It lives in the cache directory
  rather than the store, uses no WAL, rebuilds whole rather than repairing, elects
  one builder without waiting, and falls back to reading the markdown on any error
  at all. `PROJECT_MEMORY_NO_FTS5=1` forces the fallback, and CI now runs the whole
  suite twice so that path cannot rot.
- `--json` reports `served_by`, so two agents served by different paths can explain
  a difference in tail ordering rather than wondering about it.

### Fixed while measuring

- **Turkish `İ` was unfindable by its ASCII spelling**: `casefold` turns it into
  `i` plus a combining dot, which matches nothing anyone types.
- **The evaluation's own FTS5 baseline was misconfigured** — without `tokenchars
  '_'` the pre-tokenised round trip changed 73 of 486 texts — and `bm25()` weights
  are positional over every column, so passing two weights for a three-column table
  gave the title weight to the unindexed slug and left the title at 1.0. The
  title-weight regression test caught the second one.
- **The supersession tests were still weak.** The fixture is now an unlinked
  control pair: without the link the obsolete page must rank first, and adding the
  link alone must reverse it. The earlier version guarded a score comparison that
  the ranker change quietly invalidated.

### Changed

- `references/retrieval.md` reports measured numbers with paired intervals, states
  what the harness cannot tell you, and records the negative result it produced:
  no score or word-overlap threshold can separate a question the store can answer
  from one it cannot (top-hit medians 5.32 against 5.29). `SKILL.md` now tells the
  agent that a result list is not evidence that an answer exists — the previous
  wording, "if search returns nothing relevant, say so", described a case that
  almost never happens.

- **`--supersedes <slug>`.** The replaced page is stamped `status: superseded` and
  `superseded_by:`, scored at half its BM25F score and marked in every result
  line. Ranking previously had no recency or authority term and tied
  alphabetically, so a reversed decision could outrank the decision that reversed
  it — the failure the README opens with.
- **A `PreToolUse` hook that denies a hand-written page** and names
  `memory_write.py` instead. "Writes are refused, not requested" was itself a
  request while the ordinary Write tool could walk around the validator. Escape
  hatch: `PROJECT_MEMORY_ALLOW_HAND_EDIT=1`.
- **Ranking regression tests.** `W_TITLE` could be set from 5 to 0 — the parameter
  the documentation calls the one that matters — and the whole suite stayed green.
- Snippets follow the query instead of being the page's first 100 characters, and
  every result line carries the `updated` date; the header line carries the store's
  absolute path, so the documented `cat` works from any directory.
- `.memory/` in this repository, tracked on purpose. The project had none, across
  fifteen commits of exactly the work it says to record.
- The session hook fires on `resume` as well, which the test named for it did not
  actually cover.

- The documented heredoc terminator is `PMEOF`, not `EOF`: a page documenting
  heredocs ended its own body early and the shell executed the rest of the text.
- `references/page-format.md` matches the write path — `kind` is required and one
  of four values, `sources` is required, and `note` is gone from both the reference
  and the shipped template.
- `references/retrieval.md` states that the benchmark's artifacts are not in this
  repository, so its figures are reported rather than reproducible; corrects the
  stub-size units; scopes the latency table to one machine and page size; and
  replaces the claim that `grep` is never cheaper with what it actually is — faster,
  and not an alternative, because it returns an unranked list.
- README: the injection is ~1.8 KB rather than ~1.3 KB, CI runs on `main` and pull
  requests rather than every push, a user-scope install neither asks about nor
  creates a store, and Contributing names all eight files carrying the version.
- The read trigger names a class of claim instead of a list of question
  phrasings. Agents read `"why…"` / `"what did we decide…"` as exhaustive and
  answered "what do you know about this project" straight from `AGENTS.md`,
  never searching. It now fires before stating anything about the project —
  what it is, what it does, how a part works, why it is that way.
- The session hook, `SKILL.md` and the three context files say explicitly that
  `AGENTS.md` / `CLAUDE.md` / `README.md` already in context are not a substitute
  for the search: they carry instructions rather than reasons and they drift,
  while a page stays dated and sourced. Both surfaces also name what does *not*
  need a search — a command, a typo, a rename, a file the user named, general
  programming questions — so the wider trigger does not become a search before
  every turn.

### Fixed after an independent audit of the fixes below

The changes above were then audited by agents whose task was to break them. What
they found, all of it now covered by a test that fails when the fix is removed:

- **`--supersedes` copied a symlinked file into the store.** Stamping the replaced
  page walked through its path, so `ln -s ../.env .memory/env-notes.md` — blocked
  on the read path — was read and rewritten as a real page containing the secret,
  which the next search then printed. The write path now refuses to touch anything
  that is not a contained regular file.
- **A nested ```` fence still exposed a quoted heading.** The fence pattern matched
  exactly three backticks, so the first inner ``` closed a longer outer fence —
  and quoting a memory page, the case the fix was written for, requires exactly
  that. Fences are now three *or more* characters, closed CommonMark-style.
- **A repeated `## ` header in an incoming body lost its first copy** on a merge,
  because the incoming sections were built as a dict. Introduced by the in-place
  replacement fix. Same-header chunks are joined, and only the first stored
  occurrence is replaced, so a page with two identical headers is no longer
  filled with the same text twice.
- **An orphan lock defeated the locking.** A lock left by a killed writer was not
  stale for thirty seconds, so every other writer stalled for the full timeout and
  then deleted whatever lock it found — including live ones, losing 2 to 4 of 10
  writers' sections. Staleness is now decided by asking whether the owning process
  still exists, and a live holder's lock is never removed.
- **One hostile entry could take down every search**: a directory named `notes.md`,
  a broken symlink, an unreadable file — and a FIFO did not fail the search, it
  hung it forever. Only readable regular files are indexed now, and the test for
  it runs in a subprocess with a timeout so a regression fails CI instead of
  hanging it.
- **The write guard was trivially bypassable**: the extension check was
  case-sensitive, so `.memory/page.MD` was allowed and clobbers `page.md` on a
  case-insensitive filesystem; `page` with no extension was allowed too; and the
  documented `--store home` mode has no `.memory` in its path at all, so it was
  entirely unguarded. It now covers every file in a store, resolves symlinks, and
  stops over-blocking `.memory/../src/x.ts`.
- **The supersession tests were vacuous.** The whole mechanism could be deleted and
  the suite stayed green, because both fixture pages had the same title and body.
  The fixture now asserts that it is a real inversion before testing the fix.
- **The session-hook budget was only ever measured from the short in-repo path**; a
  normal install location pushed it to 2201 characters against its own 2000 limit.
  The text is shorter and the prose is bounded separately from the path.
- Self-supersession and supersession cycles are refused; an empty `--body` is
  refused rather than silently bumping `updated:`; a read-only store produces a
  refusal instead of a traceback; a killed write leaves no `.tmp` behind; a title
  ending in a quote no longer loses that character on every rewrite; and
  `memory_stats.py` reports a true median.

## [0.1.0] - 2026-08-08

### Added
- `project-memory` skill (`SKILL.md`) with read-before-answer and
  write-after-work workflows.
- `memory_search.py` — ranked search over the markdown store.
- `memory_write.py` — create/section-merge pages with stable frontmatter.
- Claude Code plugin and marketplace manifests.
- Test suite covering search, writing, frontmatter tolerance and manifests.

[Unreleased]: https://github.com/Krowli/project-memory/compare/v0.3.4...HEAD
[0.3.4]: https://github.com/Krowli/project-memory/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/Krowli/project-memory/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/Krowli/project-memory/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/Krowli/project-memory/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Krowli/project-memory/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/Krowli/project-memory/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Krowli/project-memory/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Krowli/project-memory/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Krowli/project-memory/releases/tag/v0.1.0
