# How obra/superpowers stays portable across coding agents

> **Where this lives.** `docs/research/` is new: this repository had no convention for
> research notes, so primary-source investigations now go here, one file per question.
> This note was written 2026-09-15 against superpowers **v6.3.0**.

**Sources.** `SP` below means the installed package
`/Users/krowli/.claude/plugins/cache/claude-plugins-official/superpowers/6.3.0`. Its file
tree is identical to `main` of https://github.com/obra/superpowers (the only `dev`-branch
addition is `.github/ISSUE_TEMPLATE/diagnosis_report.md`, checked with
`gh api repos/obra/superpowers/git/trees/{main,dev}?recursive=1`). Issue and PR numbers
are in that repository. Vendor docs are cited by URL; where a URL redirected, both are given.

---

## 1. Summary of the portability strategy

1. One skill tree, zero runtime dependencies, written in **action vocabulary** ("invoke a
   skill", "dispatch a subagent", "read a file") that never names a harness tool
   [`SP/docs/porting-to-a-new-harness.md` Part 1; `SP/AGENTS.md` "Third-party dependencies"].
2. Per harness, a thin adapter does exactly two things: register `skills/` with the
   harness's native skill discovery, and inject `skills/using-superpowers/SKILL.md`
   (wrapped in `<EXTREMELY_IMPORTANT>`) at session start. "The bootstrap is the entire
   integration. Without it, the skill files are inert" [`SP/docs/porting-to-a-new-harness.md` Part 1 §3].
3. Three injection shapes are recognised: **A** shell hook whose stdout JSON is read
   (Claude Code, Cursor, Copilot CLI); **B** in-process plugin that mutates the message
   array (OpenCode, Pi, Hermes); **C** manifest-declared context file (Gemini `GEMINI.md`,
   Kimi `sessionStart.skill`) [`SP/docs/porting-to-a-new-harness.md` Part 4].
4. The **no-hook fallback** is to inject nothing and rely on the harness's own skill index:
   the `using-superpowers` description ("Use when starting any conversation…") is what
   prompts the model to load it. Codex, Devin, Grok and Droid run this way
   [`SP/.codex-plugin/plugin.json` (`"hooks": {}`); PR #1995; `SP/docs/porting-to-a-new-harness.md` Part 5 case 2].
5. Codex went the other way on purpose: v5.1.0 added a Codex SessionStart hook, v6.1.0
   removed it because "Codex reliably triggers skills on its own, and the bootstrap hook
   made the UX worse rather than better" [`SP/RELEASE-NOTES.md` v6.1.0 "Codex"].
6. Nothing is ever enforced. Superpowers ships **only** a SessionStart-class hook on any
   harness; no PreToolUse/deny, no Stop hook exists anywhere in the package
   [`SP/hooks/hooks.json`, `SP/hooks/hooks-cursor.json` — sole event `SessionStart`/`sessionStart`].
   Compliance is prose ("YOU MUST invoke the skill") plus a precedence rule that user
   instruction files win [`SP/skills/using-superpowers/SKILL.md`].
7. Every harness must pass one acceptance test — "Let's make a react todo list" must
   auto-trigger `brainstorming` in a clean session — and ports that need per-session
   opt-in, copy files, or wrap with `npx skills` are rejected [`SP/AGENTS.md` "New Harness Support"].
8. Behaviour is measured, not assumed: the drill eval harness "drives real tmux sessions
   of Claude Code / Codex / Gemini CLI and judges skill compliance with an LLM verifier"
   [`SP/AGENTS.md` "Eval harness"; `SP/docs/testing.md`].
9. Rule 2 of porting: everything ships through the harness's own install mechanism;
   editing the user's `AGENTS.md`/`settings.json` is forbidden
   [`SP/docs/porting-to-a-new-harness.md` Part 1 "Two rules"].

---

## 2. Per-agent table

| Agent | (a) How it learns skills exist at session start | (b) On-demand skill loading | (c) Enforcement | (d) Install |
|---|---|---|---|---|
| **Claude Code** | Shape A. Plugin `hooks/hooks.json`: `SessionStart`, matcher `startup\|clear\|compact`, command `"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd" session-start`, `shell: bash`, `async: false` [`SP/hooks/hooks.json`]. Script `cat`s the whole `using-superpowers/SKILL.md` and prints `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":…}}` when `CLAUDE_PLUGIN_ROOT` is set and `COPILOT_CLI` is not [`SP/hooks/session-start`]. `resume` deliberately excluded [`SP/RELEASE-NOTES.md` v5.0.3 "Stop firing SessionStart hook on --resume"]. Sync because async "could fail to complete before the model's first turn" [`SP/RELEASE-NOTES.md` v4.3.0]. | Native `Skill` tool — the wrapper says "For all other skills, use the 'Skill' tool" [`SP/hooks/session-start`]. Manifest has no `skills`/`hooks` fields; Claude Code auto-discovers `skills/` and `hooks/hooks.json` [`SP/.claude-plugin/plugin.json`; `SP/docs/porting-to-a-new-harness.md` Part 4 Shape A]. | None. Only event registered is `SessionStart` [`SP/hooks/hooks.json`]. | `/plugin install superpowers@claude-plugins-official` or `/plugin marketplace add obra/superpowers-marketplace` + `/plugin install superpowers@superpowers-marketplace` [`SP/README.md`]. |
| **Codex CLI / Codex App** | **No hook, nothing injected.** `.codex-plugin/plugin.json` sets `"skills": "./skills/"` and `"hooks": {}` — the empty object is required because an absent field made Codex auto-discover and register `hooks/hooks.json` [`SP/.codex-plugin/plugin.json`; `SP/RELEASE-NOTES.md` v6.1.1]. Codex itself injects "each skill's name and description" at session start (≤2% of context / 8,000 chars) and invokes a skill implicitly "when your task matches the skill `description`" [https://developers.openai.com/codex/skills → https://learn.chatgpt.com/docs/build-skills]. So `using-superpowers`'s own description is the trigger. | Codex native: `$skill-name` or implicit; full `SKILL.md` loads "when Codex selects a skill" [same URL]. Codex-specific notes (multi_agent flag, `spawn_agent`, `wait_agent`) in `SP/skills/using-superpowers/references/codex-tools.md`. Packaged skills must each carry `agents/openai.yaml` metadata [`SP/scripts/package-codex-plugin.sh`]. | None. Codex supports plugin hooks, superpowers declines them [`SP/RELEASE-NOTES.md` v6.1.0]. | App: Plugins sidebar → Superpowers → `+`. CLI: `/plugins` → search `superpowers` → Install Plugin, from https://github.com/openai/plugins [`SP/README.md`]. Portal archive built by `SP/scripts/package-codex-plugin.sh` (ships only `.codex-plugin/`, `assets/`, `skills/`, README, LICENSE, CoC — "hooks, tests, docs, and other harness manifests are intentionally not shipped"); marketplace mirror via `SP/scripts/sync-to-codex-plugin.sh` → `prime-radiant-inc/openai-codex-plugins`. Repo doubles as a Codex marketplace via `SP/.agents/plugins/marketplace.json`. |
| **Cursor** | Shape A. `.cursor-plugin/plugin.json`: `"skills": "./skills/"`, `"hooks": "./hooks/hooks-cursor.json"` [`SP/.cursor-plugin/plugin.json`]. `hooks-cursor.json`: `"version": 1`, `sessionStart` → `./hooks/run-hook.cmd session-start` [`SP/hooks/hooks-cursor.json`]. Script prints `{"additional_context": …}` when `CURSOR_PLUGIN_ROOT` is set (checked first because Cursor may also set `CLAUDE_PLUGIN_ROOT`) [`SP/hooks/session-start`; `SP/RELEASE-NOTES.md` v5.0.3]. | Cursor native skill loading; "none needed (Claude Code–compatible tool surface)" [`SP/docs/porting-to-a-new-harness.md` Appendix A]. | None. | `/add-plugin superpowers` in Agent chat, or marketplace search [`SP/README.md`]. |
| **Gemini CLI** | Shape C. `gemini-extension.json` declares `"contextFileName": "GEMINI.md"`; `GEMINI.md` is two `@`-includes of the bootstrap skill and `references/gemini-tools.md` [`SP/gemini-extension.json`; `SP/GEMINI.md`]. Gemini: "The name of the file that contains the context for the extension. This will be used to load the context from the extension directory" [https://geminicli.com/docs/extensions/reference/]. No hook, no code. | `activate_skill` tool [`SP/skills/using-superpowers/references/gemini-tools.md`]. Gemini auto-discovers the bundled `skills/` dir ("Place skill definitions in a `skills/` directory") [https://geminicli.com/docs/extensions/reference/]. | None. Gemini extensions may ship `hooks/hooks.json`; superpowers does not [same URL; `SP` tree]. | `gemini extensions install https://github.com/obra/superpowers`; update with `gemini extensions update superpowers` [`SP/README.md`]. Removed in v6.1.0 (EOL report), restored v6.1.1 [`SP/RELEASE-NOTES.md`; #1954]. |
| **GitHub Copilot CLI** | Shape A, sharing the Claude Code files. Copilot reads legacy manifests at `.claude-plugin/plugin.json` and marketplaces at `.claude-plugin/marketplace.json` [https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference]. Same `hooks/hooks.json`; script prints top-level `{"additionalContext": …}` when `COPILOT_CLI` is set [`SP/hooks/session-start`]. Required Copilot CLI ≥ 1.0.11, whose changelog reads "sessionStart hook additionalContext is now injected into the conversation" [#792 (obra, 2026-03-25); `SP/RELEASE-NOTES.md` v5.0.7]. | Native `skill` tool — "`skill(brainstorming)`, `skill(using-superpowers)` etc. all work" [#792]. Plugin `skills/` dirs are seventh in Copilot's skill load order [cli-plugin-reference URL above]. | None. | `copilot plugin marketplace add obra/superpowers-marketplace` then `copilot plugin install superpowers@superpowers-marketplace` [`SP/README.md`]. Marketplace file: https://github.com/obra/superpowers-marketplace/blob/main/.claude-plugin/marketplace.json. |
| **OpenCode** | Shape B. `.opencode/plugins/superpowers.js` (root `package.json` `main`). `config` hook pushes the skills dir into `config.skills.paths`; `experimental.chat.messages.transform` prepends the bootstrap as a text part on the **first user message** (not a system message: #750 token bloat, #894 Qwen breaks), dedup-guarded on `EXTREMELY_IMPORTANT`, cached at module level (#1202) [`SP/.opencode/plugins/superpowers.js`]. Both hook names exist in OpenCode's plugin type but the transform is absent from the public plugins page [https://github.com/anomalyco/opencode/blob/main/packages/plugin/src/index.ts; https://opencode.ai/docs/plugins/]. | Native `skill` tool: "use skill tool to load brainstorming" [`SP/.opencode/INSTALL.md`]. OpenCode shows name+description at startup and loads the body on `skill({name})` [https://opencode.ai/docs/skills/]. | None from superpowers. (OpenCode itself offers `permission.ask`, `tool.execute.before`, and per-skill allow/deny/ask — unused.) | `opencode.json`: `"plugin": ["superpowers@git+https://github.com/obra/superpowers.git"]` [`SP/.opencode/INSTALL.md`]. |
| **Pi** | Shape B. `.pi/extensions/superpowers.ts`, declared in root `package.json` `pi.extensions` + `pi.skills: ["./skills"]` + keyword `pi-package` [`SP/package.json`]. `resources_discover` → `{skillPaths:[skillsDir]}`; `session_start`/`session_compact` arm a flag, `agent_end` clears it; `context` inserts a user-role bootstrap message after any leading `compactionSummary`, dedup marker `superpowers:using-superpowers bootstrap for pi` [`SP/.pi/extensions/superpowers.ts`]. Pi: `resources_discover` is "Fired after `session_start` so extensions can contribute additional skill, prompt, and theme paths"; `context` is "Fired before each LLM call. Modify messages non-destructively" and handlers return `{ messages }` [https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md]. | **No Skill tool.** Bootstrap says: "load the relevant `SKILL.md` with `read` when the skill applies, or let a human invoke `/skill:name` explicitly" [`SP/.pi/extensions/superpowers.ts` `piToolMapping()`; `SP/skills/using-superpowers/references/pi-tools.md`]. | None. | `pi install git:github.com/obra/superpowers`; dev: `pi -e /path/to/superpowers` [`SP/README.md`]. |
| **Kimi Code** | Shape C via manifest. `.kimi-plugin/plugin.json`: `"skills": "./skills/"`, `"sessionStart": {"skill": "using-superpowers"}`, plus `skillInstructions` tool mapping [`SP/.kimi-plugin/plugin.json`]. Kimi: `sessionStart.skill` "Loads the specified plugin Skill into the main Agent when a new or resumed session starts… It only injects text; it does not execute code"; `skillInstructions` is "appended whenever a Skill from this plugin is loaded" [https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/customization/plugins.md]. "There are no copied skills, symlinks, hooks, or extra runtime dependencies" [`SP/docs/README.kimi.md`]. | Kimi's native `Skill` tool [`SP/.kimi-plugin/plugin.json` `skillInstructions`]. | None (Kimi plugins may declare `hooks`; unused) [same Kimi URL]. | `/plugins` → Marketplace → Superpowers, or `/plugins install https://github.com/obra/superpowers`; `/new` afterwards [`SP/docs/README.kimi.md`]. |
| **Hermes Agent** | Shape B (Python). `.hermes-plugin/__init__.py` registers a `pre_llm_call` hook returning `{"context": bootstrap}` on `is_first_turn` — "on_session_start return values are ignored, and ctx.inject_message refuses from that hook — verified empirically 2026-07-23"; also `ctx.register_skill(name, Path(skill_md))` for every skill [`SP/.hermes-plugin/__init__.py`; `SP/.hermes-plugin/plugin.yaml` `provides_hooks: [pre_llm_call]`]. | `skill_view("superpowers:skill-name")`; fallback `read_file("<skills_dir>/skill-name/SKILL.md")` [`SP/.hermes-plugin/__init__.py`; `SP/skills/using-superpowers/references/hermes-tools.md`]. | None. **No post-compaction re-injection**: "a very long session that compacts over its first turn loses the bootstrap — start a fresh session" [`SP/README.md` Hermes]. | `hermes plugins install obra/superpowers --enable`, restart sessions [`SP/README.md`]. |
| **Devin CLI** | **No hook, nothing injected.** `.devin-plugin/plugin.json` has no `skills`/`hooks`/`sessionStart` fields; Devin auto-discovers co-located `skills/` [`SP/.devin-plugin/plugin.json`; `SP/tests/devin/test-devin-plugin.sh`]. PR #1995: "Devin plugins carry skills only — the plugin system has no hook or context-file component… Devin natively surfaces every installed skill's name + description in the system prompt at session start, with a standing instruction to invoke any matching skill immediately via its native `skill` tool" — the porting guide's "surfaced skill index" path. Devin has a `SessionStart` hook with `hookSpecificOutput.additionalContext` but it loads only from user/project config, which rule 2 forbids editing [PR #1995 "alternatives"]. | Devin native `skill` tool [PR #1995]. | None. | `devin plugins install obra/superpowers`; `devin plugins update superpowers` [`SP/README.md`]. |
| **Antigravity CLI (`agy`)** | README claims Shape A: "Antigravity runs the plugin's session-start hook, so Superpowers is active from the first message" [`SP/README.md`]. The porting guide instead describes an `.antigravity-plugin/install.sh` generating an `ANTIGRAVITY.md` via `contextFileName` [`SP/docs/porting-to-a-new-harness.md` Part 6] — **that directory does not exist in v6.3.0 or on `main`**. Open issue #2247 (2026-09-02, agy 1.1.24): `hooks/hooks.json` "fails to parse" ("invalid hook \"hooks\": command hook must specify 'command'"), `SessionStart` is not a configurable agy event (only `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`), `${CLAUDE_PLUGIN_ROOT}` is never set, and agy's injection field is `injectSteps` — "the using-superpowers bootstrap never loads". Status: unresolved contradiction between README and issue. | No Skill tool; listed with Pi as "native skill discovery but no Skill tool" → read `SKILL.md` [`SP/docs/porting-to-a-new-harness.md` Part 5 case 2; `SP/skills/using-superpowers/references/antigravity-tools.md`]. | None. | `agy plugin install https://github.com/obra/superpowers` [`SP/README.md`]. |
| **Factory Droid** | Consumes the Claude Code plugin unchanged: "Factory's Droid… consumes the Claude Code plugin via its own `plugin install` command and needs no new files here" [`SP/docs/porting-to-a-new-harness.md` Part 2]. Which hook shape Droid honours: not documented in the repo. | Not documented in repo. | None documented. | `droid plugin marketplace add https://github.com/obra/superpowers` then `droid plugin install superpowers@superpowers` [`SP/README.md`]. |
| **Grok Build CLI** | No superpowers-specific files. xAI's marketplace sources the repo at a pinned SHA [https://github.com/xai-org/plugin-marketplace/blob/main/.grok-plugin/marketplace.json]. The acceptance transcript in PR #1919 shows the model calling `Skill using-superpowers` then `Skill brainstorming` unprompted — i.e. Grok surfaced the skill index natively; no bootstrap injector is involved [PR #1919]. | Grok native `Skill` tool [PR #1919 transcript]. | None. | `grok plugin install superpowers@xai-official --trust` or `/marketplace` in the TUI [`SP/README.md`]. |

**Per-harness tool-mapping references that still ship** (v6.1.0 pruned `claude-code-tools.md` and `copilot-tools.md` as having "nothing harness-specific left"): `antigravity`, `codex`, `gemini`, `hermes`, `pi` [`SP/skills/using-superpowers/references/`; `SP/RELEASE-NOTES.md` v6.1.0]. Devin's reference from PR #1995 is not present in v6.3.0.

**Version lockstep**: `SP/.version-bump.json` tracks `package.json`, `.hermes-plugin/plugin.yaml`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.devin-plugin/plugin.json`, `.kimi-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `gemini-extension.json`.

---

## 3. Verbatim bootstrap and fallback texts

### 3.1 The bootstrap skill itself — `SP/skills/using-superpowers/SKILL.md` (complete, v6.3.0)

```markdown
---
name: using-superpowers
description: Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY response including clarifying questions
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, ignore this skill.
</SUBAGENT-STOP>

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

## The Rule

**Invoke relevant or requested skills BEFORE any response or action** — including clarifying questions, exploring the codebase, or checking files. If it turns out wrong for the situation, you don't have to use it.

**Before entering plan mode:** if you haven't already brainstormed, invoke the brainstorming skill first.

Then announce "Using [skill] to [purpose]" and follow the skill exactly. If it has a checklist, create a todo per item.

## Skill Priority

When multiple skills apply, process skills come first — they set the approach, then implementation skills (frontend-design, etc.) carry it out. Brainstorming and systematic-debugging are Superpowers' most common process skills, but the rule holds for any of them.

- "Let's build X" → superpowers:brainstorming first, then implementation skills.
- "Fix this bug" → superpowers:systematic-debugging first, then domain skills.

## Red Flags

These thoughts mean STOP—you're rationalizing:

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Check for skills. |
| "I need more context first" | Skill check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "I can check git/files quickly" | Files lack conversation context. Check for skills. |
| "Let me gather information first" | Skills tell you HOW to gather information. |
| "This doesn't need a formal skill" | If a skill exists, use it. |
| "I remember this skill" | Skills evolve. Read current version. |
| "This doesn't count as a task" | Action = task. Check for skills. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "I'll just do this one thing first" | Check BEFORE doing anything. |
| "This feels productive" | Undisciplined action wastes time. Skills prevent this. |
| "I know what that means" | Knowing the concept ≠ using the skill. Invoke it. |

## Platform Adaptation

If your harness appears here, read its reference file for special instructions:

- Codex: `references/codex-tools.md`
- Pi: `references/pi-tools.md`
- Antigravity: `references/antigravity-tools.md`
- Hermes Agent: `references/hermes-tools.md`

## User Instructions

User instructions (CLAUDE.md, AGENTS.md, GEMINI.md, etc, direct requests) take precedence over skills, which in turn override default behavior. Only skip skill workflows or instructions when your human partner has explicitly told you to.
```

On the no-injector harnesses (Codex, Devin, Grok, Droid) the `description:` line above is the *entire* session-start bootstrap — it is what the harness's own skill index shows the model.

### 3.2 Shell-hook wrapper — Claude Code, Cursor, Copilot CLI (`SP/hooks/session-start`)

The script wraps the whole file above (frontmatter included) as:

```
<EXTREMELY_IMPORTANT>
You have superpowers.

**Below is the full content of your 'superpowers:using-superpowers' skill - your introduction to using skills. For all other skills, use the 'Skill' tool:**

${using_superpowers_escaped}
</EXTREMELY_IMPORTANT>
```

and emits exactly one of three JSON shapes, chosen by environment variable (the test suite asserts the *other* fields are absent — Claude Code reads both `additional_context` and `hookSpecificOutput` "without deduplication") [`SP/hooks/session-start`; `SP/tests/hooks/test-session-start.sh`]:

| Harness | Detection | stdout |
|---|---|---|
| Cursor | `CURSOR_PLUGIN_ROOT` set | `{"additional_context": "…"}` |
| Claude Code | `CLAUDE_PLUGIN_ROOT` set, `COPILOT_CLI` unset | `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "…"}}` |
| Copilot CLI / unknown | else (`COPILOT_CLI=1`) | `{"additionalContext": "…"}` |

Windows fallback in the dispatcher: "No bash found - exit silently rather than error (plugin still works, just without SessionStart context injection)" [`SP/hooks/run-hook.cmd`].

### 3.3 OpenCode in-process wrapper (`SP/.opencode/plugins/superpowers.js`)

```
<EXTREMELY_IMPORTANT>
You have superpowers.

**IMPORTANT: The using-superpowers skill content is included below. It is ALREADY LOADED - you are currently following it. Do NOT use the skill tool to load "using-superpowers" again - that would be redundant.**

${content}

**Tool Mapping for OpenCode:**
When skills request actions, substitute OpenCode equivalents:
- Create or update todos → `todowrite`
- `Subagent (general-purpose):` → `task` with `subagent_type: "general"`
- Invoke a skill → OpenCode's native `skill` tool
- Read files → `read`
- Create, edit, or delete files → `apply_patch`
- Run shell commands → `bash`
- Search files → `grep`, `glob`
- Fetch a URL → `webfetch`

Use OpenCode's native `skill` tool to list and load skills.
</EXTREMELY_IMPORTANT>
```

(`${content}` is `SKILL.md` with frontmatter stripped.)

### 3.4 Pi in-process wrapper — the **no-Skill-tool fallback text** (`SP/.pi/extensions/superpowers.ts`)

```
<EXTREMELY_IMPORTANT>
superpowers:using-superpowers bootstrap for pi

You have superpowers.

The using-superpowers skill content is included below and is already loaded for this Pi session. Follow it now. Do not try to load using-superpowers again.

${body}

## Pi tool mapping

Pi has native skills but does not expose Claude Code's `Skill` tool. When a Superpowers instruction says to invoke a skill, use Pi's native skill system instead: load the relevant `SKILL.md` with `read` when the skill applies, or let a human invoke `/skill:name` explicitly.

Pi's built-in coding tools are lowercase: `read`, `write`, `edit`, `bash`, plus optional `grep`, `find`, and `ls`. Use those for the corresponding actions: read a file, create or edit files, run shell commands, search file contents, find files by name, and list directories.

Pi does not ship a standard subagent tool. If a subagent tool such as `subagent` from `pi-subagents` is available, use it for Superpowers subagent workflows. If no subagent tool is available, do the work in this session or explain the missing capability instead of inventing `Task` calls.

Pi does not ship a standard task-list tool. If an installed todo/task tool is available, use it. Otherwise track work in plan files or a repo-local `TODO.md` when task tracking is needed. Treat older `TodoWrite` references as this task-tracking action.
</EXTREMELY_IMPORTANT>
```

### 3.5 Hermes wrapper — skill-loading fallback (`SP/.hermes-plugin/__init__.py`)

```
<EXTREMELY_IMPORTANT>
superpowers:using-superpowers bootstrap for hermes

You have superpowers.

The using-superpowers skill content is included below and is already loaded for this Hermes session. Follow it now. Do not try to load using-superpowers again.

{body}

## Loading Superpowers Skills on Hermes

Superpowers skills are registered with Hermes' native skill loader: invoke one with `skill_view("superpowers:skill-name")` (for example `skill_view("superpowers:brainstorming")`). If a namespaced lookup returns 'not found', read the skill file directly instead:
`read_file("{skills_dir}/skill-name/SKILL.md")`

The superpowers skills directory is: `{skills_dir}`

{tool_mapping}
</EXTREMELY_IMPORTANT>
```

### 3.6 Gemini context file (`SP/GEMINI.md`, complete)

```
@./skills/using-superpowers/SKILL.md
@./skills/using-superpowers/references/gemini-tools.md
```

No "already loaded" preamble: "for an `@`-include harness the content is the active instruction set, not a skill the model would re-load" [`SP/docs/porting-to-a-new-harness.md` Step 3 Shape C].

### 3.7 Kimi manifest (`SP/.kimi-plugin/plugin.json`, relevant fields)

```json
"skills": "./skills/",
"sessionStart": { "skill": "using-superpowers" },
"skillInstructions": "Kimi Code tool mapping for Superpowers skills:\n\n- When a Superpowers skill says to ask the user … call Kimi Code's `AskUserQuestion` tool. …\n- When a Superpowers skill refers to `TodoWrite`, use Kimi Code's `TodoList` tool.\n- When a Superpowers skill says `Task tool (general-purpose)` … use Kimi Code's `Agent` tool with a Kimi subagent type. …\n- When a Superpowers skill refers to the `Skill` tool, use Kimi Code's native `Skill` tool. …"
```

### 3.8 The documented fallback for harnesses with no hook and no context file

From `SP/docs/porting-to-a-new-harness.md` Part 5, case 2 ("surfaced skill index"):

> If there's no context-file field but the harness surfaces each installed skill's name + description at session start, you need *neither* a built index nor a runtime-list instruction — the harness is the index, and `using-superpowers`'s own surfaced description can be what triggers the model to load it. This is softer than a declared context file; two things it does **not** give you … **It bootstraps *triggering*, not the *tool mapping*.** … **There's no structural guarantee the trigger fires.** No `<EXTREMELY_IMPORTANT>` wrapper, no dedup, no re-injection after compaction — firing depends on the model choosing to act on a description it sees in the index. This is exactly why the acceptance test is mandatory here: it is the *only* guarantee.

And case 3 (no skill system at all): "the *only* mechanism is the model reading `SKILL.md` on demand … You must supply a discovery path … (b) instruct the model to list `skills/*/SKILL.md` at runtime and read their frontmatter to find a match — slower but never stale. Prefer (b)."

Part 6 escalation order when an installer strips undeclared files: ship a manifest-declared context file → "lean on the installed `using-superpowers` skill itself" → "If neither works, the harness cannot be cleanly supported yet — **say so** and raise it, rather than hand-editing the user's config."

---

## 4. Author statements and issues

### Design statements (Jesse Vincent / maintainers)

- Original announcement (2025-10-09): the SessionStart bootstrap "teaches Claude a couple important things: 1. You have skills. They give you Superpowers. 2. Search for skills by running a script and use skills by reading them and doing what they say. 3. If you have a skill to do something, you _must_ use it to do that activity." [https://blog.fsck.com/2025/10/09/superpowers/]
- OpenCode post (2025-11-24): "_Unlike_ Codex, OpenCode supports `hooks`, so Superpowers is able to automatically set itself up at session start without you needing to add lines to your `AGENTS.md` file." and "The bootstrap is what tells OpenCode that it has Superpowers. It kicks off at startup (and after compact)." [https://blog.fsck.com/2025/11/24/Superpowers-for-OpenCode/] (At that time Codex support was a Node CLI plus "Bootstrap integration with minimal AGENTS.md for automatic startup" [`SP/RELEASE-NOTES.md` v3.3.0]; that was replaced by native discovery in v4.2.0.)
- Contributor rules: "A real integration loads the `using-superpowers` bootstrap at session start. The bootstrap is what causes skills to auto-trigger at the right moments. Without it, the skills are dead weight — present on disk but never invoked." … "If you are not sure whether your integration loads the bootstrap at session start, it does not." … "Skills are not prose — they are code that shapes agent behavior." [`SP/AGENTS.md`, identical to `SP/CLAUDE.md`]
- Porting guide: "The harness must let you inject text into the model's context **at the start of every session, with no per-session opt-in by your human partner.** This is the one non-negotiable capability." and "**A hook *system* is not a session-start *event*.** … (One real harness only exposed pre/post-tool and stop events; the `SessionStart` strings were telemetry.)" [`SP/docs/porting-to-a-new-harness.md` Part 2, Part 4]
- Why no hook on Codex: "Codex no longer ships a SessionStart hook. Codex reliably triggers skills on its own, and the bootstrap hook made the UX worse rather than better." [`SP/RELEASE-NOTES.md` v6.1.0]; the `hooks: {}` follow-up because "with no `hooks` field, Codex fell back to auto-discovering `hooks/hooks.json` … and re-registered it along with its install-time trust prompt" [v6.1.1].
- Cost of injection: "The `using-superpowers` bootstrap is injected into every session, so its size is paid for constantly." [`SP/RELEASE-NOTES.md` v6.1.0]
- Sync vs async hook: "When async, the hook could fail to complete before the model's first turn, meaning using-superpowers instructions weren't in context for the first message." [`SP/RELEASE-NOTES.md` v4.3.0]
- Precedence: "If CLAUDE.md or AGENTS.md says 'don't use TDD' and a skill says 'always use TDD,' the user's instructions win." [`SP/RELEASE-NOTES.md` v5.0.0]; obra in #750: "Superpowers has explicit instructions to prefer your instructions to its own internal instructions … You shouldn't need a specialized config file."
- Model/harness dependence, obra in #699: "The skills aren't written specifically for Claude Code and Claude models — we support Codex, Gemini CLI, and others… Model tier matters more than model family."
- Capability degradation: "On harnesses with subagent support (Claude Code, Codex), subagent-driven-development is required. Executing-plans is reserved for harnesses without subagent capability, and now tells the user that Superpowers works better on a subagent-capable platform." [`SP/RELEASE-NOTES.md` v5.0.0]
- Platform-neutral rewrite (v6.0.0): "The skills used to speak Claude Code's dialect — 'use the Task tool,' 'put it in CLAUDE.md.' This release rewrites that vocabulary in terms of what you're actually doing … Prose that named 'Claude' now says 'your agent.'" [`SP/RELEASE-NOTES.md` v6.0.0; specs `SP/docs/superpowers/specs/2026-05-05-platform-neutral-{prose,config-refs,readme}-design.md`]. Side effect: the reframe made Claude Code reach for `AskUserQuestion` in brainstorming (#1773, filed by obra, closed 2026-09-03 as no longer reproducing on 6.3.0).

### Measurements

- Evals run on real sessions: "Drill (the harness) drives real tmux sessions of Claude Code / Codex / Gemini CLI and judges skill compliance with an LLM verifier." [`SP/AGENTS.md`]
- Skill-text ablation measured cross-harness: deleting TDD's "Why Order Matters" section "measurably degraded test-first behavior under 'just write it, tests after' pressure (control 8/10 → treatment 5/10, corroborated on Claude and Codex)" [`SP/RELEASE-NOTES.md` v6.2.0].
- Codex efficiency campaign (2026-07-30): "60–78% of `wait_agent` calls time out in every corpus"; "9/9 depth-2 spawns … were implementer-issued reviewers" — fixed by editing `codex-tools.md` prose, graded by scorers before merge [`SP/docs/superpowers/specs/2026-07-30-codex-efficiency-fixes-design.md`].

### Issues about skills being ignored or bootstrap not arriving

| # | Harness | Finding | State |
|---|---|---|---|
| #128 (obra, 2025-11-28) | Gemini CLI (early MCP-server attempt) | "GEMINI.md is Advisory, Not Executable. Unlike Claude Code's session hooks which inject mandatory instructions, Gemini CLI treats GEMINI.md as context/background information… **Result**: All ignored… **The only reliable approach**: User must explicitly ask for a skill by name." | Closed 2026-03-17; superseded by the `contextFileName` extension that shipped in v4.x [`SP/RELEASE-NOTES.md` v4.0.x "Gemini CLI extension"] |
| #792 (obra, 2026-03-17) | Copilot CLI | Skills loaded and "Agent uses skills proactively when descriptions match", but plugin `sessionStart` output was discarded (`l => {}` in app.js) and `AGENTS.md` is not read from plugin dirs. | Closed 2026-03-25 after Copilot CLI 1.0.11 honoured `additionalContext` |
| #1087, #1492 | OpenCode | `config` hook silently ignored / `skill` function tool absent from agent tool list, so `skill(name=…)` fails and "Agent has no fallback mechanism → skips silently". | Closed (fixed in dev / upstream) |
| #2197 | OpenCode `opencode run` | Skills register but bootstrap absent in non-interactive runs; "so they don't reliably check skills before acting — the exact failure mode the bootstrap exists to prevent." Maintainer (via Claude) could not confirm from source; asked for a marker test. | Open |
| #2160 | OpenCode subagents | Bootstrap injected into task subagents; `<SUBAGENT-STOP>` "relies on the model correctly recognising and prioritising that instruction. In practice this is not reliable." (worker invoked `brainstorming` instead of implementing). | Open |
| #2299 | Claude Code + other plugins | The "1%" directive "applies globally to *every* installed skill from *every* enabled plugin … no way to soften or disable it without disabling the entire plugin". | Closed 2026-09-14 |
| #1442 | all | "The current `SessionStart` hook is the only event surface, and it's one-shot at session boot." Requests lifecycle events (PlanWritten, TaskCompleted…). | Open |
| #2247 | Antigravity | hooks.json unparseable; no SessionStart event; bootstrap never loads (see table §2). | Open |
| #1827, #1867 | Codex App (Windows) | SessionStart hook "hook exited with code 1" / Git Bash invocation fails in sandbox — part of why the Codex hook was dropped in v6.1.0. | Closed |
| #2081, #2091, #2105, #2189 | Claude Code on Windows/WSL/VS Code | Shell-hook fragility: ~2 s of subprocess spawns per start/compact; `${CLAUDE_PLUGIN_ROOT}` not substituted or backslashed; PowerShell execution. | Open |
| #1883 | Codex | Codex-visible skills carried Claude-Code tool names (`TodoWrite`, `Task`); obra: "This should not be the case as of superpowers 6." | Closed |

---

## 5. Hook-support survey (vendor docs, one line each)

- **Codex CLI** — yes. https://developers.openai.com/codex/hooks (308 → https://learn.chatgpt.com/docs/hooks): `SessionStart`, `SessionEnd`, `SubagentStart`, `SubagentStop`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `PreCompact`, `PostCompact`, `UserPromptSubmit`, `Stop`, `Interrupt`; context injection on `SessionStart`/`SubagentStart`/`UserPromptSubmit`/`PostToolUse`; blocking on `PreToolUse`/`PermissionRequest`/`UserPromptSubmit`/`Stop`/`SubagentStop`; "When a plugin is enabled, Codex can load lifecycle hooks from that plugin" via `.codex-plugin/plugin.json` `hooks` or `hooks/hooks.json`; disable with `[features] hooks = false`. Plugins doc (https://developers.openai.com/codex/plugins → https://learn.chatgpt.com/docs/plugins): manifest fields `skills`, `hooks`, `mcpServers`, `interface`; marketplace `.agents/plugins/marketplace.json`. Superpowers ships `"hooks": {}` anyway.
- **Cursor** — yes. https://cursor.com/docs/agent/hooks: `sessionStart`/`sessionEnd`, `preToolUse`/`postToolUse`/`postToolUseFailure`, `subagentStart`/`subagentStop`, `beforeShellExecution`/`afterShellExecution`, `beforeMCPExecution`/`afterMCPExecution`, `beforeReadFile`/`afterFileEdit`, `beforeSubmitPrompt`, `preCompact`, `stop`, `afterAgentResponse`/`afterAgentThought`; returns `permission: allow|deny|ask`, `additional_context`, `followup_message`. Plugin manifest `hooks` field = "Path to hooks config file, or inline hook config" and "replaces folder discovery for that component" [https://cursor.com/docs/reference/plugins].
- **Gemini CLI** — yes. https://geminicli.com/docs/hooks/: `SessionStart` (Inject Context), `SessionEnd`, `BeforeAgent` (Block Turn / Context), `AfterAgent` (Retry / Halt), `BeforeModel`, `AfterModel`, `BeforeToolSelection`, `BeforeTool` (Block Tool / Rewrite), `AfterTool`, `PreCompress`, `Notification`; extensions ship them in `hooks/hooks.json` — "hooks are not defined in the gemini-extension.json manifest" [https://geminicli.com/docs/extensions/reference/]. Superpowers uses `contextFileName` instead of a hook.
- **OpenCode** — yes. https://opencode.ai/docs/plugins/: `tool.execute.before`/`after` (examples deny `.env` reads), `permission.asked`/`replied`, `session.created`/`compacted`/`idle`/…, `experimental.session.compacting`, `shell.env`, custom `tool`s. The plugin type additionally declares `config`, `chat.message`, `permission.ask` (`status: ask|deny|allow`), `experimental.chat.messages.transform`, `experimental.chat.system.transform` [https://github.com/anomalyco/opencode/blob/main/packages/plugin/src/index.ts] — the two transform hooks superpowers depends on are **not on the public plugins page** (page fetched 2026-09-15; strings absent). Skills have `allow`/`deny`/`ask` permissions [https://opencode.ai/docs/skills/].
- **GitHub Copilot** — yes for CLI and cloud agent. https://docs.github.com/en/copilot/reference/hooks-reference: `sessionStart` ("can inject `additionalContext`"), `sessionEnd`, `userPromptSubmitted`, `userPromptTransformed`, `preToolUse` (`permissionDecision: allow|deny|ask`; "fail-closed on errors"; exit 2 = deny), `postToolUse`, `postToolUseFailure`, `agentStop`, `subagentStart`/`subagentStop`, `errorOccurred`, `preCompact`, `notification`, `permissionRequest`; "Hooks contributed by installed plugins — declared by each plugin in its own `hooks.json`" are in the load order. The Agent Skills concept page mentions no hook mechanism [https://docs.github.com/en/copilot/concepts/agents/about-agent-skills]. Plugin manifest lookup includes `.claude-plugin/plugin.json` [https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference].
- **Kimi Code** — yes. Plugin manifest `hooks` "Hook rules run on lifecycle events while enabled", same fields as `[[hooks]]` in `config.toml`; env `KIMI_PLUGIN_ROOT` [https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/customization/plugins.md]. Event list: not fetched (in `hooks.md` of the same docs).
- **Pi** — extension events, not shell hooks: `session_start`, `resources_discover`, `session_compact`, `context` (mutate messages), `tool_call` ("**Can block.** … `{ block: true, reason?, terminate? }`"), `agent_end`/`agent_settled` [https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md].
- **Hermes Agent** — Python plugin hooks `pre_tool_call`, `post_tool_call`, `pre_llm_call`, `post_llm_call`, `on_session_start`, `on_session_end` [https://github.com/NousResearch/hermes-agent/blob/main/plugins/AGENTS.md].
- **Devin CLI** — `SessionStart` with `hookSpecificOutput.additionalContext`, loaded only from `.devin/hooks.v1.json` / `~/.config/devin/config.json`, not from plugins [PR #1995; vendor docs not fetched].
- **Antigravity (`agy`)** — per issue #2247 (not vendor docs): `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`; no `SessionStart`; injection via `injectSteps`. Vendor docs: not found in this research.
- **Factory Droid, Grok Build CLI** — not found in docs consulted; not documented in the superpowers repo.
- **Claude Code** (baseline) — https://code.claude.com/docs/en/hooks: `SessionStart` (matchers `startup`, `resume`, `clear`, `compact`, `fork`; `hookSpecificOutput.additionalContext`), `PreToolUse` (`permissionDecision: allow|deny`, exit 2 blocks), `Stop` (`decision: block` + `reason`; exit 2 "Prevents Claude from stopping"), plus `UserPromptSubmit`, `PostToolUse`, `SubagentStart/Stop`, `PreCompact`/`PostCompact`, `SessionEnd`, and others; "Define plugin hooks in `hooks/hooks.json`".

Agent Skills spec, for reference: name+description "are loaded at startup for all skills"; "The full `SKILL.md` body is loaded when the skill is activated"; the spec defines no hook, enforcement or session-start mechanism (only an experimental `allowed-tools` frontmatter field) [https://agentskills.io/specification].

---

## 6. What this means for a skill that today relies on SessionStart, PreToolUse and Stop hooks

**Mechanisms superpowers proves work on every harness it supports**

1. *Session-start prose injection* — but through a different transport per harness, and never through the user's own instruction file:
   - shell hook, stdout JSON, field name per harness (Claude Code `hookSpecificOutput.additionalContext`; Cursor `additional_context`; Copilot `additionalContext`) [`SP/hooks/session-start`];
   - in-process message mutation as a **user** message (OpenCode transform; Pi `context`; Hermes `pre_llm_call` context) [`SP/.opencode/plugins/superpowers.js`; `SP/.pi/extensions/superpowers.ts`; `SP/.hermes-plugin/__init__.py`];
   - manifest-declared context file or session-start skill (Gemini `contextFileName`; Kimi `sessionStart.skill`) [`SP/gemini-extension.json`; `SP/.kimi-plugin/plugin.json`];
   - **no injection at all**, relying on the harness surfacing the skill's `description` (Codex, Devin, Grok; Droid via the Claude manifest) [`SP/.codex-plugin/plugin.json`; PR #1995; PR #1919].
   The compaction case is covered only where the transport allows it: Claude Code matcher `compact`, Pi `session_compact`, OpenCode per-step re-injection; Hermes explicitly loses the bootstrap after compaction [`SP/README.md`].
2. *On-demand skill body loading* via the harness's skill tool, with `read SKILL.md` as the sanctioned fallback where no such tool exists (Pi, Antigravity, Hermes fallback) [`SP/docs/porting-to-a-new-harness.md` Step 5].
3. *Prose-only compliance*, with an explicit precedence rule that instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) beat the skill [`SP/skills/using-superpowers/SKILL.md` "User Instructions"] and an acceptance test run per harness as the only guarantee it fires [`SP/AGENTS.md`].
4. *A hook is optional even where it exists*: on Codex the maintainers found the native skill index sufficient and the hook harmful [`SP/RELEASE-NOTES.md` v6.1.0].

**Mechanisms superpowers uses only on Claude Code (or not at all)**

- `hooks/hooks.json` with `${CLAUDE_PLUGIN_ROOT}`, matcher `startup|clear|compact`, `shell: "bash"`, `async: false` is Claude-Code-specific syntax; Cursor needs `hooks-cursor.json` (`version: 1`, lowercase `sessionStart`, relative command) and Copilot reuses the Claude file only because it reads `.claude-plugin/` manifests [`SP/hooks/hooks.json`; `SP/hooks/hooks-cursor.json`; Copilot cli-plugin-reference].
- **PreToolUse (allow/deny) and Stop hooks are used by superpowers on no harness at all.** Every superpowers hook file registers exactly one event, session start. The vendor docs above show deny-capable pre-tool events on Claude Code, Codex, Cursor, Gemini (`BeforeTool`), Copilot, OpenCode (`permission.ask`, `tool.execute.before`), Pi (`tool_call` block), Hermes (`pre_tool_call`), Kimi, and Antigravity — but superpowers provides no evidence that a plugin-shipped deny hook is honoured on any of them, and its own distribution disables hooks entirely on Codex (`hooks: {}`), ships none for Gemini/Kimi/OpenCode/Pi/Hermes, and cannot ship them for Devin (plugins carry skills only).
- Stop-class events exist under different names and semantics — Claude Code `Stop` (blocks), Codex `Stop` (blocks), Copilot `agentStop`, Cursor `stop` (`followup_message`), Gemini `AfterAgent` (Retry / Halt), Pi `agent_end`/`agent_settled` (notification), Hermes `on_session_end`, Antigravity `Stop` — with no cross-harness plugin packaging demonstrated by superpowers.
- Therefore a skill whose correctness depends on SessionStart + PreToolUse + Stop has, on the superpowers evidence, exactly one portable layer: the session-start prose and the skill's `description`. Everything the deny and stop hooks currently guarantee would have to be restated as prose in the bootstrap (the way `<SUBAGENT-STOP>` and "User instructions … take precedence" are), accepting the documented failure modes: model-dependent compliance (#2160), missing injection in headless modes (#2197), loss after compaction on some harnesses (Hermes), and no trigger guarantee on index-only harnesses (`SP/docs/porting-to-a-new-harness.md` Part 5 case 2).
