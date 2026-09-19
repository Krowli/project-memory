# Project memory

Gemini CLI expands `@path`, so this file is one line rather than a third copy of a
contract that has to stay in step. `AGENTS.md` is the rendered instruction block
and `src/pagelore/data/AGENT.md` is where it comes from; a test fails if those two
drift, and a copy here would be the one nobody notices going stale.

@AGENTS.md

In a clone there is no installed `lore` yet, so run the module directly from the
repository root: `python3 -m pagelore search "your query"`. `pip install -e .` puts
`lore` on PATH and the commands in the block work verbatim. `CLAUDE.md` carries the
same note plus how to work on this repository.
