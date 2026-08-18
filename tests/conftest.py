import os
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1] / "skills" / "project-memory"
sys.path.insert(0, str(SKILL / "scripts"))


@pytest.fixture()
def store(tmp_path):
    """An empty memory store in a temp dir."""
    d = tmp_path / ".memory"
    d.mkdir()
    return d


@pytest.fixture()
def populated(store):
    import memory_write
    memory_write.write_page(
        store, "webgl-context-loss", "xterm WebGL context loss on display sleep",
        "bug", ["src/terminal/renderer.ts"],
        "## Cause\n\nThe WebGL renderer loses its context when the display sleeps.\n")
    memory_write.write_page(
        store, "command-palette-highlight", "Command palette match highlighting",
        "concept", [],
        "## Context\n\nFuzzy match ranges are highlighted in the palette.\n")
    # Bilingual page: the corpus mixes Russian and English.
    memory_write.write_page(
        store, "sqlite-writer-ownership", "Кто пишет в coordination.db",
        "decision", ["src-tauri/src/database.rs"],
        "## Решение\n\nТолько MCP сервер пишет в базу. Frontend uses Tauri commands.\n")
    return store


WINDOWS = sys.platform == "win32"

# `os.geteuid` and `os.mkfifo` do not exist on Windows, and file modes there do not
# mean what chmod means on POSIX — a 0o500 directory stays writable. Tests that
# depend on either are skipped rather than faked, so the Windows run reports what
# it actually covered.
needs_posix = pytest.mark.skipif(WINDOWS, reason="POSIX-only: file modes, mkfifo, euid")


def is_root() -> bool:
    return not WINDOWS and os.geteuid() == 0
