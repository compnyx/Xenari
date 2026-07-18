"""Focused Xenari behavior tests."""

import subprocess
import sys
from types import SimpleNamespace

import pytest

from xenari.cli.commands import COMMAND_HANDLERS
from xenari.cli.handlers import maintenance
from xenari.cli.parser import COMMANDS

from .support import REPO


def test_every_parser_command_has_exactly_one_handler():
    assert set(COMMANDS) == {"help", *COMMAND_HANDLERS}


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
