"""Two agents writing the same slug must not lose each other's work.

Subagent fan-out makes this ordinary rather than exotic: several agents finish
related work at the same time and record it against the same page. The write is
a read-modify-write over a whole file, so without a lock the loser's section
disappears while both commands exit 0.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] / "skills" / "project-memory"
          / "scripts" / "memory_write.py")

WRITERS = 12
FILLER = ("The reap loop waits on the child before closing the master fd, so a child "
          "that ignores SIGTERM keeps the fd open and waitpid never returns. " * 3)


def test_parallel_writes_to_one_slug_all_survive(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    store = tmp_path / ".memory"

    def write(i):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--store", str(store), "--slug", "shared",
             "--title", "Shared page", "--kind", "concept", "--source", "src/real.ts",
             "--body", f"## Section {i:02d}\n\n{FILLER}\n"],
            capture_output=True, text=True, cwd=tmp_path)

    with ThreadPoolExecutor(max_workers=WRITERS) as pool:
        results = list(pool.map(write, range(WRITERS)))

    assert [r.returncode for r in results] == [0] * WRITERS, [r.stderr for r in results]
    body = (store / "shared.md").read_text(encoding="utf-8")
    missing = [i for i in range(WRITERS) if f"## Section {i:02d}" not in body]
    assert not missing, f"sections lost: {missing}"


def test_a_page_is_never_observed_half_written(tmp_path):
    """The page was rewritten in place, so a reader could parse a truncated file
    and rank the fragment as the page's real content."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    store = tmp_path / ".memory"
    sys.path.insert(0, str(SCRIPT.parent))
    import memory_lib
    import memory_write

    memory_write.write_page(store, "p", "T", "concept", ["src/real.ts"],
                            "## One\n\n" + FILLER)
    page = store / "p.md"
    seen = []

    def reader():
        # Through the product's own read path, which is what a search uses and
        # which absorbs the Windows sharing violation a raw read would raise.
        for _ in range(400):
            seen.append(memory_lib.read_text(page).count("---"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        r = pool.submit(reader)
        for i in range(40):
            memory_write.write_page(store, "p", "T", "concept", ["src/real.ts"],
                                    f"## One\n\n{i} {FILLER}")
        r.result()

    assert set(seen) == {2}, "frontmatter delimiters seen incomplete: a partial page was read"


def test_the_lock_leaves_nothing_behind(tmp_path):
    sys.path.insert(0, str(SCRIPT.parent))
    import memory_write
    store = tmp_path / ".memory"
    memory_write.write_page(store, "p", "T", "concept", [], "## One\n\nbody\n")
    assert [p.name for p in store.iterdir() if p.suffix == ".lock"] == []


def test_the_log_survives_parallel_appends(tmp_path):
    """Every line must stay parseable: a torn line is tolerated by the reader,
    but it still loses an event."""
    sys.path.insert(0, str(SCRIPT.parent))
    import memory_lib
    store = tmp_path / ".memory"
    memory_lib.ensure_store(store)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: memory_lib.log_event(store, "search", query=f"q{i}" * 40),
                      range(200)))

    lines = (store / memory_lib.LOG_NAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 200
    for line in lines:
        json.loads(line)


def test_a_lock_left_by_a_dead_process_is_taken_over_at_once(tmp_path):
    """The first version treated staleness as a clock: a lock younger than 30s
    blocked every writer for the full timeout, and then each of them unlinked
    whatever lock it found — including live ones. Measured: 2 to 4 of 10 writers
    lost their section, every process exiting 0."""
    import time

    import memory_lib
    store = tmp_path / ".memory"
    memory_lib.ensure_store(store)
    page = store / "p.md"

    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock = page.with_name(f".{page.name}.lock")
    lock.write_text(f"{dead.pid} {memory_lib._boot_id()}", encoding="utf-8")

    start = time.monotonic()
    with memory_lib.page_lock(page):
        pass
    assert time.monotonic() - start < 2.0, "waited on a lock whose owner is gone"
    assert not lock.exists()


def test_a_live_holders_lock_is_never_stolen(tmp_path, monkeypatch):
    """Taking a live writer's lock away is what turned a stall into data loss."""
    import time

    import memory_lib
    monkeypatch.setattr(memory_lib, "LOCK_TIMEOUT_SECONDS", 0.3)
    store = tmp_path / ".memory"
    memory_lib.ensure_store(store)
    page = store / "p.md"

    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock = page.with_name(f".{page.name}.lock")
        lock.write_text(f"{holder.pid} {memory_lib._boot_id()}", encoding="utf-8")
        start = time.monotonic()
        with memory_lib.page_lock(page):
            pass
        assert time.monotonic() - start >= 0.3, "did not wait for the holder at all"
        assert lock.exists(), "the live holder's lock was removed"
        assert str(holder.pid) in lock.read_text(encoding="utf-8")
    finally:
        holder.kill()
        holder.wait()


def test_a_failed_write_leaves_no_temp_file_behind(tmp_path):
    import memory_lib
    store = tmp_path / ".memory"
    memory_lib.ensure_store(store)
    try:
        memory_lib.atomic_write(store / "p.md", None)  # type: ignore[arg-type]
    except TypeError:
        pass
    assert [p.name for p in store.iterdir() if p.name.endswith(".tmp")] == []


def test_liveness_never_signals_a_process_directly(tmp_path):
    """`os.kill(pid, 0)` is a liveness probe on POSIX and a kill on Windows, where
    any signal but CTRL_C/CTRL_BREAK is delivered via TerminateProcess. It may
    appear in exactly one place, behind the platform check."""
    import memory_lib
    source = Path(memory_lib.__file__).read_text(encoding="utf-8")
    lines = source.splitlines()
    calls = [n for n, line in enumerate(lines) if line.strip().startswith("os.kill(")]
    assert len(calls) == 1, f"os.kill called on {len(calls)} lines, expected 1"

    start = next(n for n, line in enumerate(lines) if line.startswith("def _process_alive"))
    end = next(n for n, line in enumerate(lines) if line.startswith("def _owner_is_gone"))
    assert start < calls[0] < end, "os.kill is called outside the platform-guarded probe"
    probe = "\n".join(lines[start:end])
    assert 'os.name == "nt"' in probe


def test_a_dead_process_is_reported_dead_and_a_live_one_alive():
    import os as _os

    import memory_lib
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    assert memory_lib._process_alive(dead.pid) is False
    assert memory_lib._process_alive(_os.getpid()) is True
