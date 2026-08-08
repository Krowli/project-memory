#!/usr/bin/env bash
# Install the project-memory skill for any agent that reads SKILL.md from disk.
#
#   curl -fsSL https://raw.githubusercontent.com/Krowli/project-memory/main/install.sh | bash
#   ./install.sh --project          # into ./.agents/skills (commit it with the repo)
#   ./install.sh --dest ~/.claude/skills
#
# Default target is ~/.agents/skills, the shared cross-agent location read by
# Codex, Cursor and Gemini CLI. Claude Code reads ~/.claude/skills, so we
# symlink that to the same directory rather than keeping two copies.
set -euo pipefail

REPO="${PROJECT_MEMORY_REPO:-https://github.com/Krowli/project-memory}"
REF="${PROJECT_MEMORY_REF:-main}"
NAME="project-memory"
DEST=""
SCOPE="user"

while [ $# -gt 0 ]; do
  case "$1" in
    --project) SCOPE="project"; shift ;;
    --dest)    DEST="${2:?--dest needs a path}"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$DEST" ]; then
  if [ "$SCOPE" = "project" ]; then DEST="$PWD/.agents/skills"; else DEST="$HOME/.agents/skills"; fi
fi

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git clone --depth 1 --branch "$REF" "$REPO" "$tmp/src" >/dev/null 2>&1

mkdir -p "$DEST"
rm -rf "${DEST:?}/$NAME"
cp -R "$tmp/src/skills/$NAME" "$DEST/$NAME"
echo "installed: $DEST/$NAME"

# Claude Code reads ~/.claude/skills; point it at the same directory.
if [ "$SCOPE" = "user" ] && [ -d "$HOME/.claude" ]; then
  mkdir -p "$HOME/.claude/skills"
  if [ ! -e "$HOME/.claude/skills/$NAME" ]; then
    ln -s "$DEST/$NAME" "$HOME/.claude/skills/$NAME"
    echo "linked:    $HOME/.claude/skills/$NAME -> $DEST/$NAME"
  fi
fi

python3 "$DEST/$NAME/scripts/memory_search.py" --help >/dev/null \
  && echo "verified:  scripts run under $(python3 --version)"

cat <<MSG

Next:
  1. mkdir -p .memory   (in the project whose decisions you want to record)
  2. Add the three lines from the README's AGENTS.md snippet to your AGENTS.md
     if your agent does not auto-discover skills.
MSG
