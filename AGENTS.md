# Project memory

Durable decisions, contracts and bug post-mortems live as markdown pages in
`.memory/`. Treat them as the record of why this project looks the way it does.

**Before answering "why…", "what did we decide about…", or before changing an
unfamiliar subsystem**, search first:

```bash
python3 .agents/skills/project-memory/scripts/memory_search.py "your query"
```

Read a full page with `cat .memory/<slug>.md`. If nothing relevant comes back,
say so rather than guessing.

**After an architectural decision, a non-obvious bugfix, or a contract change**,
write the page:

```bash
python3 .agents/skills/project-memory/scripts/memory_write.py \
  --slug short-kebab-slug --title "One line" --kind decision --source path/to/file
```

Skip this for typos, reverts, formatting and test-only edits. One topic per
page; cross-link with `[[other-slug]]`.
