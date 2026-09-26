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

import conftest
import pytest

WRITE = [*conftest.LORE, "write"]

WRITERS = 12
FILLER = ("The reap loop waits on the child before closing the master fd, so a child "
          "that ignores SIGTERM keeps the fd open and waitpid never returns. " * 3)


def test_parallel_writes_to_one_slug_all_survive(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    store = tmp_path / ".memory"

    def write(i):
        return subprocess.run(
            [*WRITE, "--store", str(store), "--slug", "shared",
             "--title", "Shared page", "--kind", "concept", "--source", "src/real.ts",
             "--body", f"## Section {i:02d}\n\n{FILLER}\n"],
            capture_output=True, text=True, cwd=tmp_path, env=conftest.lore_env())

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
    from pagelore import lib as memory_lib
    from pagelore import write as memory_write

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
    from pagelore import write as memory_write
    store = tmp_path / ".memory"
    memory_write.write_page(store, "p", "T", "concept", [], "## One\n\nbody\n")
    assert [p.name for p in store.iterdir() if p.suffix == ".lock"] == []


def test_the_log_survives_parallel_appends(tmp_path):
    """Every line must stay parseable: a torn line is tolerated by the reader,
    but it still loses an event."""
    from pagelore import lib as memory_lib
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

    from pagelore import lib as memory_lib
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

    from pagelore import lib as memory_lib
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
    from pagelore import lib as memory_lib
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
    from pagelore import lib as memory_lib
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

    from pagelore import lib as memory_lib
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    assert memory_lib._process_alive(dead.pid) is False
    assert memory_lib._process_alive(_os.getpid()) is True


class _FakeKernel32:
    """The three calls the Windows probe makes, answering as Windows does for a
    process that has exited and been reaped: nobody holds a handle, so it does not
    open, and the error is ERROR_INVALID_PARAMETER."""

    def __init__(self, error):
        self.error = error

    def OpenProcess(self, access, inherit, pid):
        return 0

    def GetExitCodeProcess(self, handle, code):
        raise AssertionError("never reached without a handle")

    def CloseHandle(self, handle):
        raise AssertionError("never reached without a handle")


def test_a_reaped_process_is_dead_on_windows_too():
    """The probe answered "no such process" with alive. A lock whose owner had
    exited was then never taken over: on a Windows runner every waiter sat out the
    sixty-second timeout and all of them wrote unlocked at once, losing sections
    while every command exited 0. Decided without Windows by handing the probe the
    answers Windows gives."""
    from pagelore import lib as memory_lib
    probe = memory_lib._windows_process_alive
    assert probe(4242, _FakeKernel32(87), lambda: 87) is False, "no such process"
    assert probe(4242, _FakeKernel32(5), lambda: 5) is True, "exists, not ours"
    assert probe(4242, _FakeKernel32(1), lambda: 1) is None, "cannot say"


@pytest.mark.skipif(sys.platform != "win32", reason="the real API, on the platform it answers")
def test_a_reaped_child_is_reported_dead():
    """The existing liveness test asks about a child whose Popen still holds a
    handle, which is the one case in which a dead process still opens."""
    import gc

    from pagelore import lib as memory_lib
    pid = int(subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                             capture_output=True, text=True, check=True).stdout)
    gc.collect()
    assert memory_lib._process_alive(pid) is False


def test_a_release_the_os_refuses_for_a_moment_still_removes_the_lock(tmp_path, monkeypatch):
    """Windows refuses to delete a file another process has open, and a waiter
    reading the owner out of the lock is exactly that. The release gave up on the
    first refusal and left the lock behind; measured on a Windows runner, that is
    how every lost section began. Simulated: the first few deletes are refused."""
    from pagelore import lib as memory_lib
    store = tmp_path / ".memory"
    memory_lib.ensure_store(store)
    page = store / "p.md"
    lock = page.with_name(f".{page.name}.lock")

    real_unlink = Path.unlink
    refusals = []

    def unlink(self, *args, **kwargs):
        if self == lock and len(refusals) < 3:
            refusals.append(self)
            raise PermissionError(13, "The process cannot access the file because it "
                                      "is being used by another process")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    with memory_lib.page_lock(page) as held:
        assert held.held
    assert len(refusals) == 3
    assert not lock.exists(), "the lock outlived its release"


def test_a_lock_being_deleted_is_waited_for_not_skipped(tmp_path, monkeypatch):
    """Windows refuses to create a file that is still being deleted, and says
    "access denied" rather than "exists". The lock took any error but "exists" to
    mean the store could not be locked at all and wrote unlocked at once — in the
    middle of the write whose release it had just watched begin. Simulated: the
    first few creates are refused that way."""
    import os as _os

    from pagelore import lib as memory_lib
    store = tmp_path / ".memory"
    memory_lib.ensure_store(store)
    page = store / "p.md"
    lock = page.with_name(f".{page.name}.lock")

    real_open = _os.open
    refusals = []

    def refusing_open(path, flags, *args):
        if Path(path) == lock and len(refusals) < 3:
            refusals.append(path)
            raise PermissionError(13, "Access is denied")
        return real_open(path, flags, *args)

    monkeypatch.setattr(memory_lib.os, "open", refusing_open)
    with memory_lib.page_lock(page) as held:
        assert held.held, "went on unlocked on a transient refusal"
    assert len(refusals) == 3


def test_an_unlocked_writer_notices_it_was_overwritten_and_writes_again(tmp_path, monkeypatch):
    """The lock is advisory: after the timeout a writer proceeds without it, because
    losing a section is bad and recording nothing is worse. That leaves a window in
    which another writer can overwrite this one between its read and its write, and a
    Windows runner with twelve writers on one slug found it — section 00 vanished while
    every command exited 0.

    Simulated rather than raced, so it is the same test on every machine: the lock
    reports that it was not held, and the page is clobbered once, exactly in the gap.
    """
    from pagelore import lib as memory_lib
    from pagelore import write as memory_write

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    store = tmp_path / ".memory"
    monkeypatch.chdir(tmp_path)

    memory_write.write_page(store, "shared", "Shared page", "concept",
                            ["src/real.ts"], f"## Section 00\n\n{FILLER}\n")
    page = store / "shared.md"
    theirs = page.read_text(encoding="utf-8")

    monkeypatch.setattr(memory_lib.page_lock, "__enter__",
                        lambda self: setattr(self, "held", False) or self)
    writes = []
    real = memory_lib.atomic_write

    def clobbered_once(path, text):
        real(path, text)
        writes.append(text)
        if len(writes) == 1:        # the other writer lands in the gap, exactly once
            real(path, theirs)

    monkeypatch.setattr(memory_lib, "atomic_write", clobbered_once)
    monkeypatch.setattr(memory_write, "atomic_write", clobbered_once)

    memory_write.write_page(store, "shared", "Shared page", "concept",
                            ["src/real.ts"], f"## Section 01\n\n{FILLER}\n")

    body = page.read_text(encoding="utf-8")
    assert len(writes) > 1, "an unlocked write that was overwritten did not try again"
    assert "## Section 01" in body, "the retry did not restore the lost section"
    assert "## Section 00" in body, "the retry dropped the other writer's section"
