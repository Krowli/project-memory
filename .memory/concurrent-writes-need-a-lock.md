---
slug: concurrent-writes-need-a-lock
title: "Two agents on one slug silently lost each other's sections"
kind: bug
created: 2026-08-17
updated: 2026-08-17
sources:
  - skills/project-memory/scripts/memory_lib.py
  - tests/test_concurrency.py
---

## Cause

A write parses the page, merges in memory and rewrites the whole file. There was
no lock, no `O_EXCL` and no re-read before writing, so a writer that finished
between another writer's parse and write was overwritten entirely. Both commands
exited 0.

Measured with twelve to twenty unmodified `memory_write.py` subprocesses writing
distinct sections of the same slug, with no instrumentation and no artificial
window: five runs lost 1, 1, 16, 0 and 1 of 20 sections. Subagent fan-out makes
this ordinary rather than exotic — several agents finish related work at the same
time and record it against the same page.

Rewriting in place also truncated the file first, so a concurrent search could
parse a half-written page and rank the fragment as the page's real content, and a
crash in that window left the page permanently short with no backup.

## Fix

An advisory lock file per page, taken with `O_CREAT|O_EXCL`, and the content
replaced through a temp file plus `os.replace` so a reader never sees a partial
page. The lock is self-healing: one older than 30 seconds is assumed to belong to
a dead process, and after 10 seconds the write proceeds regardless. Losing a
section is bad; refusing to record anything because of a stale file on disk is
worse.

The log is appended with one `O_APPEND` `os.write` per line, so parallel writers
cannot interleave halves of two records into one unparseable line.
