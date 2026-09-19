---
slug: concurrent-writes-need-a-lock
title: "Two agents on one slug silently lost each other's sections"
kind: bug
created: 2026-08-17
updated: 2026-09-19
sources:
  - src/pagelore/lib.py
  - src/pagelore/write.py
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

## What the lock still did not cover

The per-page lock is advisory on purpose: after `LOCK_TIMEOUT_SECONDS` a writer
proceeds without it, because losing a section is bad and refusing to record anything
is worse. That leaves one window, and on 2026-09-19 a Windows CI runner found it.
Twelve writers on one slug, which is what subagent fan-out produces, and section 00
vanished while every one of the twelve commands exited 0. The exact failure this page
was written about, returning through the escape hatch built into its own fix.

Two causes, both of them a number tuned on the wrong machine.

The timeout was ten seconds, chosen against a fast POSIX filesystem. A dead holder is
already handled at once and separately by `_owner_is_gone`, so the timeout only ever
has to cover a holder that is alive and slow. Twelve Windows processes, each paying
interpreter startup and a virus scanner per file write, ran past ten seconds. It is
now sixty, which costs nothing when there is no contention.

And the escape hatch itself never checked its own work. An unlocked write now re-reads
the page afterwards, and if its own `## ` headers are not there it merges and writes
again, three times at most. Three because each attempt is a full read-merge-write and
the case it covers is already a writer that could not get a lock for a minute; looping
past that trades a possible lost section for a command that never returns.

## The scratch file was named by pid alone

Found while writing the test for the above. `atomic_write` built its temporary file as
`.<page>.<pid>.tmp`, so two threads in one process picked the same name and each
deleted or replaced the other's — `os.replace` then raised FileNotFoundError on a file
that had existed a moment earlier. One process per write is the shipped shape, so this
never fired in production, but `write_page` is importable and `evals/mcp_probe.py`
calls it directly. The name now carries the thread id too.
