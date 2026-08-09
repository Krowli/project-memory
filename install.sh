#!/usr/bin/env bash
# Install the project-memory skill for any agent that reads SKILL.md from disk.
#
#   curl -fsSL https://raw.githubusercontent.com/Krowli/project-memory/main/install.sh | bash
#   ./install.sh --project                    # skill into ./.agents/skills
#   ./install.sh --dest ~/.claude/skills
#   ./install.sh --store home                 # skip the storage question
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
REF="${PROJECT_MEMORY_REF:-main}"
NAME="project-memory"
DEST=""
SCOPE="user"
STORE_MODE="${PROJECT_MEMORY_STORE:-}"
NO_STORE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project)  SCOPE="project"; shift ;;
    --dest)     DEST="${2:?--dest needs a path}"; shift 2 ;;
    --store)    STORE_MODE="${2:?--store needs gitignored|tracked|home}"; shift 2 ;;
    --no-store) NO_STORE=1; shift ;;
    -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
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

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

# ── the skill ────────────────────────────────────────────────────────────────
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git clone --depth 1 --branch "$REF" "$REPO" "$tmp/src" >/dev/null 2>&1

mkdir -p "$DEST"
rm -rf "${DEST:?}/$NAME"
cp -R "$tmp/src/skills/$NAME" "$DEST/$NAME"
echo "skill:     $DEST/$NAME"

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

python3 "$DEST/$NAME/scripts/memory_search.py" --help >/dev/null \
  && echo "verified:  scripts run under $(python3 --version)"
# The verification run leaves bytecode behind; drop it so the install is exactly
# the files from the repository.
rm -rf "$DEST/$NAME/scripts/__pycache__"

[ "$NO_STORE" = "1" ] && { echo; echo "Store not created (--no-store)."; exit 0; }

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

cat <<MSG

Next: add the snippet from this repo's AGENTS.md to your project's AGENTS.md if
your agent does not discover skills on its own.
MSG
