"""Focused Xenari behavior tests."""

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from xenari.cli import commands
from xenari.cli.commands import COMMAND_HANDLERS
from xenari.cli.handlers import maintenance
from xenari.cli.parser import COMMANDS, build_parser

from .support import REPO


def test_every_parser_command_has_exactly_one_handler():
    assert set(COMMANDS) == {"help", *COMMAND_HANDLERS}


def test_subcommands_expose_only_command_specific_options():
    parser = build_parser()

    search = parser.parse_args(["search", "danger", "--limit", "3"])
    assert search.command == "search"
    assert search.limit == 3
    assert not hasattr(search, "tense")

    speak = parser.parse_args(["speak", "I love you", "--tense", "past"])
    assert speak.command == "speak"
    assert speak.tense == "past"
    assert not hasattr(speak, "limit")

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["stats", "--limit", "1"])
    assert exc.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["stats"],
        ["search", "dangerous", "--limit", "2"],
        ["duplicates", "--limit", "1", "--format", "json"],
        ["pos", "verb", "--limit", "1", "--format", "json"],
        ["pos-set", "see", "toq", "verb", "--dry-run"],
        ["pos-backfill", "--dry-run"],
        ["categorize", "--root", "anhthu"],
        ["relate", "brak", "plonq", "--relation", "synonym", "--dry-run"],
        ["add", "byte", "qevk", "byte", "--dry-run"],
        ["export", "json"],
        ["export", "md", "out.md"],
    ],
)
def test_db_only_invocations_select_the_lightweight_runtime(argv):
    args = build_parser().parse_args(argv)
    assert commands._uses_database_runtime(args)


@pytest.mark.parametrize(
    "argv",
    [
        ["lookup", "love"],
        ["inspect", "fatyih"],
        ["translate", "I love you"],
        ["doctor"],
        ["parity"],
        ["gaps", "script.txt"],
        ["sync"],
        ["coin", "glimmer", "soft unsteady light"],
        ["export", "js"],
        ["export", "site"],
    ],
)
def test_translation_and_cross_component_invocations_keep_the_full_runtime(argv):
    args = build_parser().parse_args(argv)
    assert not commands._uses_database_runtime(args)


def test_db_only_command_does_not_construct_translation_facade(monkeypatch):
    opened = []

    class FakeDatabase:
        def __init__(self, *, read_only):
            opened.append({"read_only": read_only, "closed": False})

        def stats(self):
            return "tiny runtime"

        def close(self):
            opened[-1]["closed"] = True

    monkeypatch.setattr(commands, "XenariDB", FakeDatabase)

    commands.main(["stats"])

    assert opened == [{"read_only": True, "closed": True}]


@pytest.mark.parametrize("command", sorted(commands.DB_MUTATION_COMMANDS))
def test_confirmed_mutations_request_a_writable_runtime(command):
    args = build_parser().parse_args([command, "--yes"])
    assert commands._requires_db_write(args)


@pytest.mark.parametrize("command", sorted(commands.DB_MUTATION_COMMANDS))
def test_preview_mutations_request_a_read_only_runtime(command):
    args = build_parser().parse_args([command])
    assert not commands._requires_db_write(args)


def test_cli_closes_the_facade_when_a_handler_raises(monkeypatch):
    closed = []

    class FakeRuntime:
        def close(self):
            closed.append(True)

    def fail(_args, _x):
        raise RuntimeError("handler failed")

    monkeypatch.setattr(commands, "_open_runtime", lambda _args: FakeRuntime())
    monkeypatch.setitem(commands.COMMAND_HANDLERS, "stats", fail)

    with pytest.raises(RuntimeError, match="handler failed"):
        commands.main(["stats"])

    assert closed == [True]


def test_cli_reports_an_unavailable_writable_canon_cleanly(monkeypatch, capsys):
    def refuse(_args):
        raise RuntimeError("explicit writable db_path required")

    monkeypatch.setattr(commands, "_open_runtime", refuse)

    with pytest.raises(SystemExit) as exc:
        commands.main(["add", "--yes"])

    assert exc.value.code == 1
    assert "explicit writable db_path required" in capsys.readouterr().err


def test_help_does_not_open_the_database(monkeypatch, capsys):
    def unexpected(_args):
        raise AssertionError("help must not open the canon")

    monkeypatch.setattr(commands, "_open_runtime", unexpected)

    commands.main(["help"])

    assert "Xenari" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("command", "usage"),
    [
        ("compound", "Usage: compound"),
        ("speak", "Usage: speak"),
        ("gloss", "Usage: gloss"),
        ("translate", "Usage: translate"),
        ("reverse", "Usage: reverse"),
        ("llm-context", "Usage: llm-context"),
        ("llm-lint", "Usage: llm-lint"),
    ],
)
def test_translation_commands_reject_missing_input(run_cli, command, usage):
    result = run_cli(command)

    assert result.returncode == 1
    assert usage in result.stdout


def test_info_exits_nonzero_when_any_requested_root_is_unknown(run_cli):
    known = run_cli("info", "zrent")
    assert known.returncode == 0
    assert "zrent — love" in known.stdout

    mixed = run_cli("info", "zrent", "definitely-not-a-root")
    assert mixed.returncode == 1
    assert "zrent — love" in mixed.stdout
    assert "definitely-not-a-root — unknown root" in mixed.stdout


def test_duplicates_cli_is_explicitly_read_only_and_machine_readable(run_cli):
    result = run_cli("duplicates", "--limit", "1", "--format", "json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["write_performed"] is False
    assert payload["count"] >= len(payload["candidates"]) == 1
    assert payload["candidates"][0]["rows"]

    filtered = run_cli(
        "duplicates", "--confidence", "high", "--kind", "possible_synonym",
        "--limit", "2", "--format", "json", check=True,
    )
    filtered_payload = json.loads(filtered.stdout)
    assert all(row["confidence"] == "high" for row in filtered_payload["candidates"])
    assert all(row["kind"] == "possible synonym" for row in filtered_payload["candidates"])


def test_part_of_speech_cli_reports_senses_and_previews_without_writing(run_cli):
    before = (REPO / "xenari.db").read_bytes()

    report = run_cli("pos", "--format", "json", check=True)
    payload = json.loads(report.stdout)
    assert payload["schema_present"] is True
    assert payload["annotated"] > 0

    verbs = run_cli("pos", "verb", "--limit", "2", "--format", "json", check=True)
    verb_rows = json.loads(verbs.stdout)
    assert len(verb_rows) == 2
    assert all(row["part_of_speech"] == "verb" for row in verb_rows)

    preview = run_cli("pos-set", "see", "toq", "verb", "--dry-run", check=True)
    assert "POS preview: see -> toq = verb" in preview.stdout

    backfill = run_cli("pos-backfill", "--dry-run", check=True)
    assert "POS backfill preview" in backfill.stdout
    assert (REPO / "xenari.db").read_bytes() == before

    unknown = run_cli("pos", "--unknown", "--limit", "2", "--format", "json", check=True)
    unknown_rows = json.loads(unknown.stdout)
    assert len(unknown_rows) == 2
    assert all("english_key" in row and "root" in row for row in unknown_rows)

    proposals = run_cli("pos", "--proposals", "--format", "json", check=True)
    assert isinstance(json.loads(proposals.stdout), list)


def test_structured_translation_reports_and_benchmark_are_machine_readable(run_cli):
    complete = json.loads(run_cli("speak", "I love you", "--format", "json", check=True).stdout)
    assert complete["schema"] == "xenari.translation_report.v1"
    assert complete["status"] == "complete"
    assert complete["confidence"] == "high"

    partial = json.loads(run_cli("speak", "Run!", "--format", "json", check=True).stdout)
    assert partial["status"] == "partial"
    assert partial["diagnostics"] == ["[partial: unsupported imperative: run]"]

    reverse = json.loads(
        run_cli("reverse", "ra blorq ka neq ta zrent sa xo", "--format", "json", check=True).stdout
    )
    assert reverse["direction"] == "xenari_to_english"
    assert reverse["status"] in {"partial", "unsupported"}

    benchmark = json.loads(
        run_cli("benchmark", "--iterations", "2", "--format", "json", check=True).stdout
    )
    assert benchmark["iterations"] == 2
    assert set(benchmark["milliseconds_per_operation"]) == {
        "lookup", "search", "forward", "reverse"
    }
    assert all(value >= 0 for value in benchmark["milliseconds_per_operation"].values())

    release_check = json.loads(run_cli("check", "--format", "json", check=True).stdout)
    assert release_check["schema"] == "xenari.release_check.v1"
    assert release_check["ok"] is True
    assert release_check["errors"] == {}
    assert all(release_check["checks"].values())


@pytest.mark.parametrize(
    "argv",
    [
        ["lookup", "love"],
        ["inspect", "fatyih", "--limit", "1"],
        ["info", "zrent"],
        ["validate", "zrent"],
        ["categories"],
        ["search", "dangerous", "--limit", "1"],
        ["near", "danger", "--limit", "1"],
        ["relations", "brak"],
        ["pos", "--format", "json"],
        ["pos", "--unknown", "--limit", "1"],
        ["pos", "--proposals", "--format", "json"],
        ["compound", "red", "dog"],
        ["speak", "I love you"],
        ["speak", "Run!", "--format", "json"],
        ["gloss", "I love you"],
        ["translate", "I love you"],
        ["reverse", "ra mex ka neq ta zrent sa xo"],
        ["llm-context", "I love you"],
        ["llm-lint", "ra mex ka neq ta zrent sa xo"],
        ["stats"],
        ["meta"],
        ["audit", "1"],
        ["lint", "1"],
        ["workbench", "--limit", "1"],
        ["curate", "--phrases", "--limit", "1"],
        ["duplicates", "--limit", "1", "--format", "json"],
        ["benchmark", "--iterations", "1", "--format", "json"],
        ["check", "--format", "json"],
    ],
)
def test_read_only_handlers_execute_in_process(argv, xenari, capsys):
    args = build_parser().parse_args(argv)
    COMMAND_HANDLERS[args.command](args, xenari)
    assert capsys.readouterr().out.strip()


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
