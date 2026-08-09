# Project memory

Installed as a plugin, Claude Code loads the full contract from
`skills/project-memory/SKILL.md` on its own — this file exists for the case where
the repository is cloned rather than installed, and for other tools that read
`CLAUDE.md` directly.

Durable decisions, contracts and bug post-mortems live as markdown pages in
`.memory/`.

**Before answering "why…", "what did we decide about…", or before changing an
unfamiliar subsystem**, search first:

```bash
python3 .agents/skills/project-memory/scripts/memory_search.py "your query"
```

Query words are OR'd and ranked, so give several. Read a full page with
`cat .memory/<slug>.md`. If nothing relevant comes back, say so rather than
guessing.

**After an architectural decision, a non-obvious bugfix, or a contract change**,
write the page:

```bash
python3 .agents/skills/project-memory/scripts/memory_write.py \
  --slug short-kebab-slug --title "One line" --kind decision \
  --source path/to/file --body -   <<'EOF'
## Cause

What a future agent could not reconstruct from the code...
EOF
```

The script validates and rejects: no sources, a source path that does not exist,
a body too short to be worth keeping. A rejection exits non-zero and prints a
`FIX:` line with the command to run instead — follow it rather than writing the
markdown file by hand.

Skip this for typos, reverts, formatting and test-only edits. One topic per
page; cross-link with `[[other-slug]]`.
