#!/usr/bin/env bash
# Install the project-memory skill for any agent that reads SKILL.md from disk.
#
#   curl -fsSL https://raw.githubusercontent.com/Krowli/project-memory/main/install.sh | bash
#   ./install.sh --project                    # skill into ./.agents/skills
#   ./install.sh --dest ~/.claude/skills
#   ./install.sh --store home                 # skip the storage question
#   ./install.sh --no-store                   # install the skill and nothing else
#   ./install.sh --check                      # what is installed, and is there anything newer
#   ./install.sh --uninstall                  # remove the skill; your notes are left alone
#   ./install.sh --interpreter py             # force the Python the install is verified with
#
# By default this installs the latest released tag, not the tip of main, so an
# install is reproducible and a version number means something. Set
# PROJECT_MEMORY_REF to take a branch or a specific tag instead.
#
# With no flags it installs once for every project (~/.agents/skills), which is
# what you usually want: the skill is one program, the notes are per project and
# appear on their own the first time an agent writes in a repository.
#
# Two separate things get placed, and they are not the same decision:
#
#   the SKILL   — code, safe to commit, goes to .agents/skills or ~/.agents/skills
#   the STORE   — your notes, may contain anything you write, and is asked about
#
# Store modes (--store):
#   gitignored   .memory/ in the project, added to .gitignore   [default]
#   tracked      .memory/ in the project, committed with the repo
#   home         ~/.project-memory/<project>/, symlinked as .memory/ and ignored
#
# The default is `gitignored` because the failure it prevents is one-way: notes
# pushed to a remote cannot be unpublished. Choose `tracked` deliberately, when
# you want the record reviewed in pull requests and shared with the team.
set -euo pipefail

REPO="${PROJECT_MEMORY_REPO:-https://github.com/Krowli/project-memory}"
REF="${PROJECT_MEMORY_REF:-}"
NAME="project-memory"
DEST=""
SCOPE="user"
STORE_MODE="${PROJECT_MEMORY_STORE:-}"
NO_STORE=0
CHECK=0
UNINSTALL=0
PYTHON="${PROJECT_MEMORY_PYTHON:-}"

while [ $# -gt 0 ]; do
  case "$1" in
    --project)  SCOPE="project"; shift ;;
    --dest)     DEST="${2:?--dest needs a path}"; shift 2 ;;
    --store)    STORE_MODE="${2:?--store needs gitignored|tracked|home}"; shift 2 ;;
    --no-store) NO_STORE=1; shift ;;
    --check)    CHECK=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --interpreter) PYTHON="${2:?--interpreter needs a command}"; shift 2 ;;
    -h|--help)  sed -n '2,33p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

case "${STORE_MODE:-}" in
  ""|gitignored|tracked|home) ;;
  *) echo "--store must be gitignored, tracked or home (got: $STORE_MODE)" >&2; exit 2 ;;
esac

if [ -z "$DEST" ]; then
  if [ "$SCOPE" = "project" ]; then DEST="$PWD/.agents/skills"; else DEST="$HOME/.agents/skills"; fi
fi

# ── removal ──────────────────────────────────────────────────────────────────
# Before the git and Python checks, because taking the skill off a machine must
# not depend on the toolchain that put it there. It removes exactly what the
# install created and says what it deliberately left: the pages are the user's,
# and a program that can delete them by accident is worse than no uninstaller.
if [ "$UNINSTALL" = "1" ]; then
  target="$DEST/$NAME"
  removed=0

  # Claude Code reads the skill through a symlink the install made. Only a link
  # that resolves to the directory being removed is ours; one pointing anywhere
  # else belongs to someone, and guessing by name would delete their work.
  if [ -d "$target" ]; then
    real="$(cd "$target" && pwd -P)"
    for link in "$HOME/.claude/skills/$NAME" "$PWD/.claude/skills/$NAME"; do
      if [ -L "$link" ] && [ -d "$link" ] && [ "$(cd "$link" && pwd -P)" = "$real" ]; then
        rm -f "$link"
        echo "removed:   $link"
        removed=1
      fi
    done
    rm -rf "$target"
    echo "removed:   $target"
    removed=1
  fi

  [ "$removed" = "1" ] || echo "nothing to remove: no skill at $target"

  cat <<'MSG'

Left alone on purpose:
  .memory/ in your projects   your pages — delete a store yourself if you mean to
  your agent's instruction file   remove the line naming this skill by hand
  any agent definition you wrote   yours to keep or delete
MSG
  exit 0
fi

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }

# ── scope ────────────────────────────────────────────────────────────────────
# Asked only when it is a real question: a terminal to answer on, no --project
# or --dest already deciding it, and a repository under foot for option 2 to
# mean anything. Run from nowhere in particular, or piped through CI, it stays
# global without stalling. It used to install globally in silence even when the
# user was standing in a project, which reads as the script having no opinion
# to offer rather than having made a choice.
if [ "$SCOPE" = "user" ] && [ -z "$DEST" ] && [ -r /dev/tty ] \
   && git rev-parse --show-toplevel >/dev/null 2>&1; then
  here="$(git rev-parse --show-toplevel)"
  cat <<ASK

Install the skill for every project, or only for this one?

  1) every project on this machine — ~/.agents/skills  [default]
  2) only $here — .agents/skills, committed with the repo

ASK
  printf 'Choice [1]: '
  read -r scope_choice </dev/tty || scope_choice=""
  case "${scope_choice:-1}" in
    1|"") ;;
    2)    SCOPE="project"; DEST="$PWD/.agents/skills" ;;
    *)    echo "unrecognised choice, installing for every project" ;;
  esac
fi

# `python3` is not a command name you can count on. On Windows the installer puts
# `python`, `py` and `pymanager` on PATH and no `python3` at all. Resolve a
# working interpreter once, here, so the install can be verified with it; the
# agent runs the scripts with whatever `python3` its shell has, and the pointer
# files say so.
if [ -z "$PYTHON" ]; then
  for candidate in python3 python "py -3"; do
    # shellcheck disable=SC2086
    if $candidate -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' \
         >/dev/null 2>&1; then
      PYTHON="$candidate"
      break
    fi
  done
fi
[ -n "$PYTHON" ] || { echo "no Python 3.9+ found (tried python3, python, py -3)" >&2; exit 1; }

# The latest released tag, or empty if the repository has never been tagged. A
# `curl | bash` install used to take the tip of main, so two people running the
# same command on the same day could get different code and neither could say
# which version they had.
latest_tag() {
  # shellcheck disable=SC2086
  git ls-remote --tags --refs "$REPO" 2>/dev/null | $PYTHON -c '
import re, sys
tags = [m.group(1) for line in sys.stdin
        if (m := re.search(r"refs/tags/(v\d+\.\d+\.\d+)$", line.strip()))]
print(max(tags, key=lambda t: tuple(int(n) for n in t[1:].split("."))) if tags else "")
'
}

installed_version() {
  local lib="$1/$NAME/scripts/memory_lib.py"
  [ -f "$lib" ] || { echo ""; return; }
  sed -n 's/^VERSION = "\(.*\)"$/\1/p' "$lib" | head -1
}

if [ "$CHECK" = "1" ]; then
  have="$(installed_version "$DEST")"
  want="$(latest_tag)"
  echo "installed: ${have:-nothing at $DEST/$NAME}"
  echo "latest:    ${want:-no released tag yet}"
  if [ -n "$have" ] && [ -n "$want" ] && [ "v$have" != "$want" ]; then
    echo "update:    available — re-run this script to install $want"
  elif [ -n "$have" ]; then
    echo "update:    up to date"
  fi
  exit 0
fi

if [ -z "$REF" ]; then
  REF="$(latest_tag)"
  if [ -z "$REF" ]; then
    REF="main"
    echo "note:      no released tag found, installing the tip of main" >&2
  fi
fi

# ── the skill ────────────────────────────────────────────────────────────────
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git clone --depth 1 --branch "$REF" "$REPO" "$tmp/src" >/dev/null 2>&1

mkdir -p "$DEST"
rm -rf "${DEST:?}/$NAME"
cp -R "$tmp/src/skills/$NAME" "$DEST/$NAME"
echo "skill:     $DEST/$NAME  ($REF, version $(installed_version "$DEST"))"

# Claude Code reads .claude/skills; point it at the same directory rather than
# keeping a second copy that will drift.
if [ "$SCOPE" = "user" ] && [ -d "$HOME/.claude" ]; then
  mkdir -p "$HOME/.claude/skills"
  [ -e "$HOME/.claude/skills/$NAME" ] || {
    ln -s "$DEST/$NAME" "$HOME/.claude/skills/$NAME"
    echo "linked:    $HOME/.claude/skills/$NAME"
  }
elif [ "$SCOPE" = "project" ]; then
  mkdir -p "$PWD/.claude/skills"
  [ -e "$PWD/.claude/skills/$NAME" ] || {
    ln -s "../../.agents/skills/$NAME" "$PWD/.claude/skills/$NAME"
    echo "linked:    $PWD/.claude/skills/$NAME"
  }
fi

# shellcheck disable=SC2086
$PYTHON "$DEST/$NAME/scripts/memory_search.py" --help >/dev/null \
  && echo "verified:  scripts run under $($PYTHON --version) via \`$PYTHON\`"
# The verification run leaves bytecode behind; drop it so the install is exactly
# the files from the repository.
rm -rf "$DEST/$NAME/scripts/__pycache__"

# The one thing a user must do by hand, printed at the one moment they are
# looking. Without it the scripts sit on disk and the agent may never reach for
# them, which is the difference between installed and working — and the
# installer used to end without mentioning it at all.
next_steps() {
  cat <<MSG

Next: tell your agent it has a memory. One line, once.

  Claude Code     add to ~/.claude/CLAUDE.md
  Gemini CLI      add to ~/.gemini/GEMINI.md

      @$DEST/$NAME/USE.md

  Codex CLI       paste that file's contents into ~/.codex/AGENTS.md
  Cursor          paste them into Customize → Rules

Per project instead of per machine: put the same line in the project's own
CLAUDE.md or AGENTS.md. Only one agent: put it in that agent's definition.

To remove everything this installed:  ./install.sh --uninstall
MSG
}

[ "$NO_STORE" = "1" ] && { echo; echo "Store not created (--no-store)."; next_steps; exit 0; }

# A global install is not standing in any particular project, and it will meet
# many. Stores appear on their own at the first write and shield themselves as
# they are created, so there is nothing useful to ask here.
if [ "$SCOPE" = "user" ] && [ -z "$STORE_MODE" ]; then
  cat <<'MSG'

Installed for every project. A .memory/ store appears in a project the first
time an agent writes there, and is added to that project's .gitignore as it is
created — nothing to set up per project.

To commit the notes in some project instead, run this there:
  ./install.sh --project --store tracked
MSG
  next_steps
  exit 0
fi

# ── the store ────────────────────────────────────────────────────────────────
# `curl … | bash` hands the script itself to stdin, so a prompt has to read the
# terminal directly. Without one — CI, a pipeline, a container — take the safe
# default rather than hanging or silently choosing to publish someone's notes.
if [ -z "$STORE_MODE" ]; then
  if [ -r /dev/tty ]; then
    cat <<'ASK'

Where should your memory pages live?

  1) .memory/ in this project, added to .gitignore   — private, never pushed  [default]
  2) .memory/ in this project, committed to git      — reviewed in PRs, shared with the team
  3) ~/.project-memory/<project>/                    — outside the repo entirely

ASK
    printf 'Choice [1]: '
    read -r choice </dev/tty || choice=""
    case "${choice:-1}" in
      1|"") STORE_MODE="gitignored" ;;
      2)    STORE_MODE="tracked" ;;
      3)    STORE_MODE="home" ;;
      *)    echo "unrecognised choice, using the default"; STORE_MODE="gitignored" ;;
    esac
  else
    STORE_MODE="gitignored"
    echo "no terminal to ask on; store mode: gitignored (override with --store)"
  fi
fi

project_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
store="$project_root/.memory"

ignore_store() {
  local gi="$project_root/.gitignore"
  if [ -f "$gi" ] && grep -qxF '.memory/' "$gi"; then return; fi
  printf '\n# project-memory: notes stay local\n.memory/\n' >> "$gi"
  echo "ignored:   .memory/ added to .gitignore"
}

case "$STORE_MODE" in
  gitignored)
    mkdir -p "$store"; ignore_store
    echo "store:     $store  (private)" ;;
  tracked)
    mkdir -p "$store"
    # Marker so the scripts never quietly add this store to .gitignore later.
    printf 'These pages are committed on purpose. Do not gitignore this store.\n' \
      > "$store/.tracked"
    echo "store:     $store  (committed with the repo — do not write secrets here)" ;;
  home)
    target="$HOME/.project-memory/$(basename "$project_root")"
    mkdir -p "$target"
    if [ -e "$store" ] && [ ! -L "$store" ]; then
      echo "note:      $store already exists as a real directory; leaving it alone." >&2
      echo "           Move its contents to $target and delete it to finish the switch." >&2
    else
      ln -sfn "$target" "$store"
    fi
    ignore_store
    echo "store:     $target  (outside the repo, reached via .memory/ symlink)" ;;
esac

next_steps
