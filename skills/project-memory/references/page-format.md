# Page format

One file per topic at `.memory/<slug>.md`. Frontmatter is YAML-ish and parsed
leniently — treat these as the contract:

| Field | Required | Notes |
|---|---|---|
| `slug` | yes | lowercase, digits, single hyphens; matches the filename |
| `title` | yes | one line, quoted |
| `kind` | no | `decision`, `concept`, `bug`, `note` (default `note`) — a hint, not a taxonomy |
| `created` / `updated` | auto | ISO dates, managed by `memory_write.py` |
| `sources` | no | file paths this page explains |

`sources` is accepted both inline (`sources: [a.ts, b.ts]`, written by older
pages) and as a block list. The parser handles both; always emit the block form.

```markdown
---
slug: webgl-context-loss
title: "xterm WebGL context loss on display sleep"
kind: bug
created: 2026-08-08
updated: 2026-08-08
sources:
  - src/terminal/renderer.ts
---

## Cause

The WebGL renderer loses its context when the display sleeps; xterm never
repaints because the addon does not observe `webglcontextlost`.

## Fix

Listen for the event and re-attach the addon. See [[terminal-renderer-choice]].
```

## Conventions

Write the body for someone who has forgotten the incident: what was observed,
why it happened, what was decided, and what would make you revisit it. One topic
per page — if a page needs "and also", split it. Link with `[[slug]]`.
