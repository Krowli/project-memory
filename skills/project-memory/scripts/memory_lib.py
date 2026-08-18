"""Shared helpers: locating the store, parsing pages, recording what happened.
Stdlib only."""
from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# The one place the runtime knows its own version. Eight manifests carry it too,
# and a test fails if any of them drift — but none of those files is importable,
# and until this existed neither the user nor the agent could tell which version
# was actually on disk.
VERSION = "0.2.1"

STORE_ENV = "PROJECT_MEMORY_DIR"
STORE_DIRNAME = ".memory"
LOG_NAME = ".log.jsonl"
# One O_APPEND write is atomic against other processes on POSIX, and is not on
# Windows, where 17 of 200 concurrent lines went missing. This serialises the
# threads inside one process; O_APPEND still covers the cross-process case.
_LOG_LOCK = threading.Lock()
# Written by `install.sh --store tracked`: the pages here are meant to be
# committed, so nothing should quietly add them to .gitignore behind the user.
TRACKED_MARKER = ".tracked"

LOCK_STALE_SECONDS = 30.0
LOCK_TIMEOUT_SECONDS = 10.0
# Windows refuses to replace a file another process has open; POSIX never does.
REPLACE_TIMEOUT_SECONDS = 5.0


class StoreUnavailable(Exception):
    """The store path exists but cannot be used as a directory.

    `install.sh --store home` makes the store a symlink; if its target is gone,
    `Path.exists()` follows the link and reports False while `mkdir` fails. That
    used to surface as a raw FileExistsError traceback from the write path, which
    is the one shape a refusal must never take — the agent gets no FIX: line and
    no way to tell a broken store from a bad page.
    """


def find_store(start: Path | None = None) -> Path:
    """Locate the memory store: $PROJECT_MEMORY_DIR, else nearest .memory/ upward."""
    override = os.environ.get(STORE_ENV)
    if override:
        return Path(override).expanduser().resolve()
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / STORE_DIRNAME).is_dir():
            return candidate / STORE_DIRNAME
    return cur / STORE_DIRNAME


def store_problem(store: Path) -> str | None:
    """Why this path cannot hold a store, or None if it can."""
    if store.is_symlink() and not store.exists():
        return (f"{store} is a symlink whose target is missing "
                f"({os.readlink(store)})")
    if store.exists() and not store.is_dir():
        return f"{store} exists and is not a directory"
    return None


@dataclass
class Page:
    slug: str
    title: str
    body: str
    path: Path
    meta: dict = field(default_factory=dict)

    @property
    def superseded_by(self) -> str | None:
        value = self.meta.get("superseded_by")
        return str(value) if value else None

    @property
    def updated(self) -> str:
        return str(self.meta.get("updated") or self.meta.get("created") or "")


_FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _unquote(value: str) -> str:
    """Strip one matched pair of surrounding quotes, and only a matched pair.

    `.strip("\"'")` ate a real character: a title ending in a quote came back one
    character shorter on every rewrite, losing a little more each time.
    """
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value

# Keys whose value is a list even when a page carries it as a bare scalar.
# `sources: src/real.ts` parsed to a string, and set() over a string yields one
# source per character — which destroyed the page's only anchor to the code.
LIST_KEYS = ("sources", "supersedes")


def read_text(path: Path) -> str:
    """Read a page tolerantly.

    One byte of Windows-1251 pasted into one page used to end every search in the
    project with a UnicodeDecodeError, while writes to other slugs kept
    succeeding — the store grew while retrieval was dead. A replacement character
    in one page costs that page some recall; a traceback costs all of them.
    """
    return path.read_text(encoding="utf-8", errors="replace")


def parse_page(path: Path) -> Page:
    """Parse a memory page. Tolerates both inline `sources: [a, b]` and block lists."""
    raw = read_text(path)
    meta: dict = {}
    body = raw
    m = _FM.match(raw)
    if m:
        body = raw[m.end():]
        key = None
        for line in m.group(1).splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if re.match(r"^\s*-\s+", line) and key:
                meta.setdefault(key, [])
                if isinstance(meta[key], list):
                    meta[key].append(_unquote(line.split("-", 1)[1]))
                continue
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                meta[key] = [_unquote(v) for v in val[1:-1].split(",") if v.strip()]
            elif val:
                meta[key] = _unquote(val)
            else:
                meta[key] = []
    for key in LIST_KEYS:
        if isinstance(meta.get(key), str):
            meta[key] = [meta[key]]
    slug = str(meta.get("slug") or path.stem)
    title = str(meta.get("title") or slug.replace("-", " "))
    return Page(slug=slug, title=title, body=body, path=path, meta=meta)


def is_page(path: Path, root: Path) -> bool:
    """Whether this entry may be read or written as a page of `root`.

    Three separate ways a directory entry can be hostile, all seen in practice:

    - a symlink resolving outside the store. `ln -s ../.env .memory/env-notes.md`
      turned a search the agent runs on its own into an exfiltration primitive,
      ranking the secret and printing it to stdout. A symlink is also the one
      shape of this that git can carry, so it can arrive in a pull request.
    - something that is not a regular file at all: a directory named `notes.md`,
      a broken symlink, or a FIFO — which does not merely fail, it hangs every
      search forever with no timeout.
    - a file that cannot be read.

    A hard link is deliberately *not* covered: it is indistinguishable from an
    ordinary file by path, and git cannot carry one, so it needs local write
    access to the repository — at which point a page can simply be written.
    """
    try:
        if not path.is_file():
            return False
        if path.is_symlink() and root not in path.resolve().parents:
            return False
    except OSError:
        return False
    return True


def page_paths(store: Path) -> list[Path]:
    """The pages of a store: top-level `*.md`, and nothing that leaves it.

    Top-level only, because `rglob` kept an archived page indexed after the one
    archive gesture a human has (`mkdir archive; mv`) and returned two hits with
    the same slug — so the documented `cat .memory/<slug>.md` silently got the
    wrong one.
    """
    if not store.is_dir():
        return []
    root = store.resolve()
    return [p for p in sorted(store.glob("*.md")) if is_page(p, root)]


def load_pages(store: Path) -> list[Page]:
    out = []
    for path in page_paths(store):
        try:
            out.append(parse_page(path))
        except OSError:
            continue  # unreadable now; one bad entry must not end the search
    return out


def ensure_store(store: Path) -> None:
    """Create the store if it is missing, and make a brand-new one private.

    Installed globally, the skill meets projects it has never seen; the first
    write in each of them creates a store. Shielding it at creation is the only
    moment where nobody has to remember to do it — and the mistake it prevents
    (notes pushed to a remote) cannot be undone afterwards.

    Only creation triggers this. A store that already exists is left alone: if
    the line was removed, that was a decision.
    """
    problem = store_problem(store)
    if problem:
        raise StoreUnavailable(problem)
    if store.exists():
        return
    store.mkdir(parents=True, exist_ok=True)
    if (store / TRACKED_MARKER).exists():
        return
    try:
        gitignore = store.parent / ".gitignore"
        existing = read_text(gitignore) if gitignore.exists() else ""
        # `/.memory/` is the form GitHub's UI and many templates emit.
        if any(line.strip().strip("/") == store.name.strip("/")
               for line in existing.splitlines()):
            return
        prefix = "" if (not existing or existing.endswith("\n")) else "\n"
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(f"{prefix}\n# project-memory: notes stay local\n{store.name}/\n")
    except OSError:
        # A read-only checkout should not stop the write; the pages still land.
        pass


def atomic_write(path: Path, text: str) -> None:
    """Replace a file's contents in one step.

    Rewriting in place truncates first, so a concurrent search could parse a
    half-written page and rank the fragment as the page's real content, and a
    crash in that window left the page permanently short with no backup.
    """
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        # POSIX replaces a file no matter who has it open. Windows refuses with
        # WinError 5 while any reader holds a handle, and a search reading the
        # store is exactly that reader — so a concurrent search made a write fail
        # outright rather than merely wait.
        deadline = time.monotonic() + REPLACE_TIMEOUT_SECONDS
        while True:
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.01)
    except BaseException:
        tmp.unlink(missing_ok=True)  # no litter in the store on a failed write
        raise


def _process_alive(pid: int) -> bool | None:
    """Whether that process still exists. None when this platform cannot say.

    `os.kill(pid, 0)` is the POSIX idiom and is a liveness *probe* there. On
    Windows it is not: the documentation is explicit that any signal other than
    CTRL_C_EVENT and CTRL_BREAK_EVENT is delivered by calling TerminateProcess, so
    the "probe" kills the process it was asking about. Shipping that would have
    made every contended write terminate a sibling writer — CI caught it as a
    hang, which was the mild version of the symptom.
    """
    if os.name == "nt":
        try:
            import ctypes

            SYNCHRONIZE = 0x00100000
            ERROR_INVALID_PARAMETER = 87  # no process with that id
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = kernel32.OpenProcess(
                SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return kernel32.GetLastError() == ERROR_INVALID_PARAMETER
            try:
                # A process that has exited still opens successfully while anyone
                # holds a handle to it, so the handle alone means nothing. The
                # exit code does — and 259 is the one value that cannot be
                # distinguished from "running", which is why it is reserved.
                code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return None
                return code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, and is not ours to signal
    except OSError:
        return None
    return True


def _owner_is_gone(lock: Path) -> bool:
    """Whether the process that took this lock no longer exists.

    The first version of this timed out after ten seconds and then unlinked
    whatever lock it found. That is worse than no lock at all: a single orphan
    file left by a killed writer stalled every other writer for the full timeout
    and then had them delete each other's *live* locks, which lost sections
    exactly the way the lock was introduced to prevent — measured at 2 to 4 of 10
    writers, all exiting 0.

    So staleness is decided by asking the operating system whether the owner is
    still alive, not by a clock. The mtime rule stays only as a fallback for a
    lock whose owner cannot be identified — an unparseable file, or one written
    on another machine on a shared filesystem.
    """
    try:
        raw = lock.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    try:
        pid = int(raw.split()[0])
    except (ValueError, IndexError):
        pid = None

    if pid is not None and raw.endswith(_boot_id()):
        if pid == os.getpid():
            return False
        alive = _process_alive(pid)
        if alive is not None:
            return not alive

    try:
        return (time.time() - lock.stat().st_mtime) > LOCK_STALE_SECONDS
    except OSError:
        return False


def _boot_id() -> str:
    """Identifies this host, so a PID written on another machine sharing the
    filesystem is never mistaken for a live local process. Deliberately not a
    boot timestamp: two processes must compute the same string, and any clock
    arithmetic drifts between them."""
    return platform.node() or "unknown-host"


class page_lock:
    """Serialise read-modify-write on one page across processes.

    A write parses the page, merges in memory and rewrites the whole file. Two
    agents on the same slug — ordinary with subagent fan-out — meant the second
    writer's whole section disappeared while both commands exited 0. Measured
    before this existed: concurrent writers lost up to 16 of 20 sections.

    Advisory: after LOCK_TIMEOUT_SECONDS the write proceeds without the lock
    rather than failing, because losing a section is bad but refusing to record
    anything at all is worse. It never removes a lock whose owner is alive.
    """

    def __init__(self, path: Path):
        self.lock = path.with_name(f".{path.name}.lock")
        self.fd: int | None = None

    def __enter__(self) -> page_lock:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                self.fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(self.fd, f"{os.getpid()} {_boot_id()}".encode())
                return self
            except FileExistsError:
                if _owner_is_gone(self.lock):
                    try:
                        self.lock.unlink()
                    except OSError:
                        pass
                    continue
                if time.monotonic() > deadline:
                    # Proceed unlocked. Do NOT unlink: the holder is alive, and
                    # taking its lock away is what turned a stall into data loss.
                    return self
                time.sleep(0.02)
            except OSError:
                return self  # a store we cannot lock is still a store we can write

    def __exit__(self, *exc) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            try:
                self.lock.unlink()
            except OSError:
                pass


def log_event(store: Path, event: str, *, create: bool = False, **fields) -> None:
    """Append one JSON line to the store's log. Never raises.

    Without this there is no way to answer how often the write gate fired and on
    what, except from memory — and a check whose result nobody collects is
    indistinguishable from no check. The log also captures the queries actually
    asked, which is the only honest basis for re-tuning ranking later.

    It holds real queries and slugs, so it is shielded from git inside the store
    rather than relying on the store's own mode.

    `create` is the write path's flag, and only the write path's. A refusal is
    often the very first thing that happens in a new project, so it has to be
    able to create the store it shields. A search must not: logging a miss used
    to mkdir a store and append three lines to the project's .gitignore on the
    first exploratory query in a repository that never opted in, which is a
    read-only operation dirtying a working tree.
    """
    try:
        if create:
            ensure_store(store)
        elif not store.is_dir():
            return
        ignore = store / ".gitignore"
        if not ignore.exists():
            with ignore.open("w", encoding="utf-8") as fh:
                fh.write(f"# holds every query and refusal; never commit it\n{LOG_NAME}\n")
        record = {"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                  "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False) + "\n"
        # One O_APPEND write() per line, so parallel writers cannot interleave
        # halves of two records into one unparseable line.
        with _LOG_LOCK:
            fd = os.open(store / LOG_NAME, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
    except Exception:
        # Telemetry must never be the reason a write or a search fails.
        pass
