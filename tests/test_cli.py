"""Focused Xenari behavior tests."""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from xenari.cli import commands
from xenari.cli.commands import COMMAND_HANDLERS
from xenari.cli.handlers import maintenance
from xenari.cli.parser import COMMANDS

from .support import REPO


def test_every_parser_command_has_exactly_one_handler():
    assert set(COMMANDS) == {"help", *COMMAND_HANDLERS}


@pytest.mark.parametrize(
    "argv",
    [
        ["add"],
        ["remove"],
        ["map"],
        ["categorize"],
        ["relate"],
        ["coin"],
        ["coin", "--yes", "--dry-run"],
        ["sync"],
        ["sync", "--yes"],
    ],
)
def test_preview_and_sync_invocations_open_the_canon_read_only(monkeypatch, argv):
    opened = []

    class FakeXenari:
        def __init__(self, *, read_only, site_root):
            opened.append({"read_only": read_only, "closed": False})

        def close(self):
            opened[-1]["closed"] = True

    monkeypatch.setattr(commands, "Xenari", FakeXenari)
    monkeypatch.setitem(commands.COMMAND_HANDLERS, argv[0], lambda _args, _x: None)

    commands.main(argv)

    assert opened == [{"read_only": True, "closed": True}]


@pytest.mark.parametrize("command", sorted(commands.DB_MUTATION_COMMANDS))
def test_confirmed_mutations_open_the_canon_writable(monkeypatch, command):
    opened = []

    class FakeXenari:
        def __init__(self, *, read_only, site_root):
            opened.append({"read_only": read_only, "closed": False})

        def close(self):
            opened[-1]["closed"] = True

    monkeypatch.setattr(commands, "Xenari", FakeXenari)
    monkeypatch.setitem(commands.COMMAND_HANDLERS, command, lambda _args, _x: None)

    commands.main([command, "--yes"])

    assert opened == [{"read_only": False, "closed": True}]


def test_cli_closes_the_facade_when_a_handler_raises(monkeypatch):
    closed = []

    class FakeXenari:
        def __init__(self, *, read_only, site_root):
            pass

        def close(self):
            closed.append(True)

    def fail(_args, _x):
        raise RuntimeError("handler failed")

    monkeypatch.setattr(commands, "Xenari", FakeXenari)
    monkeypatch.setitem(commands.COMMAND_HANDLERS, "stats", fail)

    with pytest.raises(RuntimeError, match="handler failed"):
        commands.main(["stats"])

    assert closed == [True]


def test_cli_reports_an_unavailable_writable_canon_cleanly(monkeypatch, capsys):
    class RefusingXenari:
        def __init__(self, **_kwargs):
            raise RuntimeError("explicit writable db_path required")

    monkeypatch.setattr(commands, "Xenari", RefusingXenari)

    with pytest.raises(SystemExit) as exc:
        commands.main(["add", "--yes"])

    assert exc.value.code == 1
    assert "explicit writable db_path required" in capsys.readouterr().err


def test_help_does_not_open_the_database(monkeypatch, capsys):
    class UnexpectedXenari:
        def __init__(self, **_kwargs):
            raise AssertionError("help must not open the canon")

    monkeypatch.setattr(commands, "Xenari", UnexpectedXenari)

    commands.main(["help"])

    assert "Xenari" in capsys.readouterr().out


def test_curate_cli_accepts_section_and_limit_flags():
    result = subprocess.run(
        [sys.executable, "xenari_tool.py", "curate", "--phrases", "--limit", "1"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Phrase-like definition review" in result.stdout
    assert "Placeholder category suggestions" not in result.stdout
    assert "Relation candidate groups" not in result.stdout

    categorize = subprocess.run(
        [sys.executable, "xenari_tool.py", "categorize", "--root", "cfolmna", "--limit", "1"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert categorize.returncode == 0
    assert "Uncategorized -> Uncategorized" in categorize.stdout
    assert "no suggestion" in categorize.stdout
    assert "PREVIEW ONLY" in categorize.stdout

    relate = subprocess.run(
        [
            sys.executable,
            "xenari_tool.py",
            "relate",
            "brak",
            "plonq",
            "--relation",
            "synonym",
            "--dry-run",
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert relate.returncode == 0
    assert "curator assertion" in relate.stdout
    assert "PREVIEW ONLY" in relate.stdout

def test_review_cli_writes_markdown_report(tmp_path):
    out = tmp_path / "xenari-qc.md"
    result = subprocess.run(
        [sys.executable, "xenari_tool.py", "review", "--limit", "1", "--output", str(out)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert f"wrote {out}" in result.stdout
    content = out.read_text(encoding="utf-8")
    assert content.startswith("# Xenari QC Review Report")
    assert "## Audit" in content
    assert "## Safe Follow-up Commands" in content

def test_failed_mutation_commands_exit_nonzero():
    cases = [
        ["add", "bad-root", "xqz", "invalid", "--yes"],
        ["map", "test-map", "not-a-root", "--yes"],
        ["remove", "not-a-root", "--yes"],
    ]
    for args in cases:
        result = subprocess.run(
            [sys.executable, "xenari_tool.py", *args],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, result.stdout + result.stderr


def test_repo_export_fails_cleanly_outside_a_source_checkout(capsys):
    class InstalledFacade:
        def export_format(self, *_args, **_kwargs):
            raise RuntimeError("generated dictionary path is source-checkout-only")

    args = SimpleNamespace(
        command="export",
        args=["repo"],
        output=None,
        site=False,
    )

    with pytest.raises(SystemExit) as exc:
        maintenance.handle(args, InstalledFacade())

    assert exc.value.code == 1
    assert "source-checkout-only" in capsys.readouterr().out
