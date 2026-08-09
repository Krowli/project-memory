"""The write path rejects pages that are not worth keeping.

This is the load-bearing idea of the skill, so it is tested at the CLI boundary
— the exit code is the contract an agent actually meets, not an internal call.

Motivation is measured, not aesthetic: in the corpus this was designed against,
104 of 495 pages were auto-generated stubs averaging 277 bytes, and they took
the top two result slots for real queries. A page nobody can trace to a file,
or one too thin to say anything the source does not, costs more than it returns.
"""
import memory_write
import pytest

LONG = ("The reap loop waits on the child before closing the master fd, so a child "
        "that ignores SIGTERM keeps the fd open and waitpid never returns. " * 3)


@pytest.fixture()
def repo(tmp_path):
    """A project root with a real file to cite and an empty store beside it."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.ts").write_text("export {}")
    (tmp_path / ".memory").mkdir()
    return tmp_path


def run(repo, *args, body=LONG):
    argv = ["--store", str(repo / ".memory")]
    if body is not None:
        argv += ["--body", body]
    return memory_write.main([*argv, *args])


def ok_args(slug="pty-hangs-on-exit"):
    return ["--slug", slug, "--title", "PTY hangs on exit", "--kind", "bug",
            "--source", "src/real.ts"]


def test_accepts_a_well_formed_page(repo):
    assert run(repo, *ok_args()) == 0
    assert (repo / ".memory" / "pty-hangs-on-exit.md").is_file()


def test_rejects_missing_sources(repo, capsys):
    rc = run(repo, "--slug", "no-sources", "--title", "T", "--kind", "bug")
    assert rc == 1
    err = capsys.readouterr().err
    assert "source" in err.lower()
    assert "FIX:" in err


def test_rejects_source_that_does_not_exist(repo, capsys):
    rc = run(repo, "--slug", "bad-source", "--title", "T", "--kind", "bug",
             "--source", "src/imaginary.ts")
    assert rc == 1
    assert "imaginary" in capsys.readouterr().err


def test_rejects_body_too_short_to_be_worth_keeping(repo, capsys):
    rc = run(repo, *ok_args(), body="Uses a mutex.")
    assert rc == 1
    err = capsys.readouterr().err
    assert str(memory_write.MIN_BODY) in err
    assert "FIX:" in err


def test_rejects_unknown_kind(repo, capsys):
    rc = run(repo, "--slug", "odd-kind", "--title", "T", "--kind", "rationale",
             "--source", "src/real.ts")
    assert rc == 1
    assert "kind" in capsys.readouterr().err.lower()


def test_requires_an_explicit_body(repo, capsys):
    """The old default wrote `## Context / TODO: why this matters.` — a stub
    generator with a friendly face."""
    rc = run(repo, *ok_args(), body=None)
    assert rc == 1
    assert "FIX:" in capsys.readouterr().err


def test_a_rejected_write_creates_no_file(repo):
    run(repo, "--slug", "never-written", "--title", "T", "--kind", "bug")
    assert not (repo / ".memory" / "never-written.md").exists()


def test_source_may_be_given_relative_to_the_store_parent(repo):
    """Agents cite paths from the repo root; the CLI may be run from elsewhere."""
    assert run(repo, *ok_args("root-relative")) == 0


def test_every_rejection_names_the_next_command(repo, capsys):
    """A rejection that does not say what to do next just teaches the agent to
    stop writing."""
    for args, body in [
        (["--slug", "a", "--title", "T", "--kind", "bug"], LONG),
        (ok_args("b"), "short"),
        (["--slug", "c", "--title", "T", "--kind", "nope", "--source", "src/real.ts"], LONG),
    ]:
        capsys.readouterr()
        assert run(repo, *args, body=body) == 1
        err = capsys.readouterr().err
        assert err.startswith("REJECTED:")
        assert "FIX:" in err
