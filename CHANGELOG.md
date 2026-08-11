# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- The read trigger names a class of claim instead of a list of question
  phrasings. Agents read `"why…"` / `"what did we decide…"` as exhaustive and
  answered "what do you know about this project" straight from `AGENTS.md`,
  never searching. It now fires before stating anything about the project —
  what it is, what it does, how a part works, why it is that way.
- The session hook, `SKILL.md` and the three context files now say explicitly
  that `AGENTS.md` / `CLAUDE.md` / `README.md` already in context are not a
  substitute for the search: they carry instructions rather than reasons and
  they drift, while a page stays dated and sourced.
- Both surfaces name what does *not* need a search — a command, a typo, a
  rename, a file the user named, general programming questions — so the wider
  trigger does not become a search before every turn.

## [0.1.0] - 2026-08-08

### Added
- `project-memory` skill (`SKILL.md`) with read-before-answer and
  write-after-work workflows.
- `memory_search.py` — ranked search over the markdown store.
- `memory_write.py` — create/section-merge pages with stable frontmatter.
- Claude Code plugin and marketplace manifests.
- Test suite covering search, writing, frontmatter tolerance and manifests.

[Unreleased]: https://github.com/Krowli/project-memory/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Krowli/project-memory/releases/tag/v0.1.0
