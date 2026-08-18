# Project memory

Durable decisions, contracts and bug post-mortems live as markdown pages in `.memory/`. Treat them as the record of why this project looks the way it does.

**Before stating anything about this project** — what it is, what it does, how a part of it works, why it is that way, what was decided or rejected — and before changing an unfamiliar subsystem, search first:

```bash
python3 ~/.agents/skills/project-memory/scripts/memory_search.py "your query"
```

The first output line is the store's absolute path; open a full page with `cat <that path>/<slug>.md`. A hit marked `⚠ superseded by <slug>` was replaced — read the replacement first. If nothing relevant comes back, say so rather than guessing.

The trigger is the kind of claim you are about to make, not the wording of the question; "how does X work" and "what do you know about this project" are memory questions too. This file is not a substitute for the search — it carries instructions rather than reasons, and it goes stale while a page stays dated and sourced. Skip the search only for mechanical work (a command, a typo, a rename) and for general programming questions.

**After an architectural decision, a non-obvious bugfix, or a contract change**, write the page:

```bash
python3 ~/.agents/skills/project-memory/scripts/memory_write.py \
  --slug short-kebab-slug --title "One line" --kind decision \
  --source path/to/file --body -   <<'PMEOF'
## Cause

What a future agent could not reconstruct from the code...
PMEOF
```

`--kind` is one of `decision`, `bug`, `concept`, `howto`. The terminator is `PMEOF`, not `EOF`, so a page that documents heredocs cannot end its own body early. When a decision reverses an earlier one, add `--supersedes <old-slug>`: that stamps the old page and demotes it, instead of leaving two pages that both read as current.

The script validates and rejects: no sources, a source path that does not exist, a resulting page too short to be worth keeping. A rejection exits non-zero and prints a `FIX:` line with the command to run instead — follow it rather than writing the markdown file by hand.

Re-running the same slug replaces same-header sections in place and appends new ones, so amendments are cheap and safe.

Skip this for typos, reverts, formatting and test-only edits. One topic per page; cross-link with `[[other-slug]]`.

The path above is the default install. With `install.sh --project` the scripts are at `.agents/skills/project-memory/scripts/` instead, and in a clone of the project-memory repository itself at `skills/project-memory/scripts/`.