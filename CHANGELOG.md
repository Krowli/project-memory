# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Krowli/project-memory/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Krowli/project-memory/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Krowli/project-memory/releases/tag/v0.1.0
