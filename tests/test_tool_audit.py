"""Regressions from the toolchain audit; mutations use tiny disposable DBs."""

import sqlite3

import pytest

from xenari import Xenari
from xenari.db import XenariDB
from xenari.services.gap import GapHarvester
from xenari.translate.report import build_translation_report


@pytest.fixture
def tiny_db(tmp_path):
    with XenariDB(tmp_path / "audit.db") as db:
        db.conn.executemany(
            "INSERT INTO roots (root, meaning) VALUES (?, ?)",
            [("xaz", "first sense"), ("fatyih", "second sense"), ("zrent", "compound")],
        )
        db.conn.commit()
        yield db


def test_failed_add_cannot_be_committed_by_next_write(tiny_db):
    tiny_db.conn.execute("""CREATE TRIGGER reject_mapping BEFORE INSERT ON english_map
        WHEN NEW.english_key = 'rejectme'
        BEGIN SELECT RAISE(ABORT, 'rejected by test'); END""")
    tiny_db.conn.commit()
    ok, _ = tiny_db.add_root("rejectme", "zakglu", "test entry")
    assert not ok
    assert not tiny_db.has_root("zakglu")
    assert not tiny_db.conn.in_transaction
    assert tiny_db.add_english_mapping("kept", "xaz")
    assert not tiny_db.has_root("zakglu")


def test_failed_remove_preserves_dependent_rows(tiny_db):
    tiny_db.add_english_mapping("kept", "xaz")
    tiny_db.conn.execute("""CREATE TRIGGER reject_delete BEFORE DELETE ON roots
        BEGIN SELECT RAISE(ABORT, 'rejected by test'); END""")
    tiny_db.conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        tiny_db.remove_root("xaz")
    assert tiny_db.has_english("kept")
    assert not tiny_db.conn.in_transaction


@pytest.mark.parametrize("dry_run", [True, False])
def test_blank_primary_key_is_rejected(tiny_db, dry_run):
    ok, _ = tiny_db.add_root("  ", "zakglu", "test entry", dry_run=dry_run)
    assert not ok
    assert not tiny_db.has_root("zakglu")
    assert not tiny_db.describe_english_mapping(" ", "xaz")[0]
    assert not tiny_db.add_english_mapping(" ", "xaz")


def test_invalid_compound_replacement_keeps_original(tiny_db):
    assert tiny_db.add_compound("zrent", ["xaz", "fatyih"])
    before = tiny_db.get_compound_parts("zrent")
    assert not tiny_db.add_compound("zrent", ["missing"])
    assert tiny_db.get_compound_parts("zrent") == before
    assert list(tiny_db.db_path.parent.glob("*.compound.bak"))


def test_search_keeps_all_senses_when_one_alias_matches(tiny_db):
    tiny_db.add_english_mapping("uniquealias", "xaz", part_of_speech="noun")
    tiny_db.add_english_mapping("otheralias", "xaz", part_of_speech="verb")
    result = tiny_db.search("uniquealias")[0]
    assert set(result["english_keys"].split(", ")) == {"uniquealias", "otheralias"}
    assert set(result["parts_of_speech"].split(",")) == {"noun", "verb"}


def test_alias_search_does_not_rescan_all_mappings_for_every_root(tiny_db):
    tiny_db.conn.executemany(
        "INSERT INTO roots (root, meaning) VALUES (?, ?)",
        [(f"test{i}", "ordinary entry") for i in range(1000)],
    )
    tiny_db.conn.execute(
        "INSERT INTO english_map (english_key, root_id) SELECT root, id FROM roots"
    )
    tiny_db.conn.commit()
    steps = 0

    def bound_work():
        nonlocal steps
        steps += 1000
        return int(steps > 200_000)

    # A VM-instruction bound detects quadratic rescanning without a flaky
    # wall-clock deadline (including on the CPU-limited test host).
    tiny_db.conn.set_progress_handler(bound_work, 1000)
    try:
        assert tiny_db.search("test999")[0]["root"] == "test999"
    finally:
        tiny_db.conn.set_progress_handler(None, 0)


def test_markdown_export_batches_categories_and_keeps_uncategorized_roots(tiny_db, tmp_path):
    tiny_db.conn.executemany(
        "INSERT INTO roots (root, meaning, category) VALUES (?, ?, ?)",
        [(f"test{i}", "entry", f"category{i}") for i in range(20)],
    )
    tiny_db.conn.commit()
    tiny_db.add_english_mapping("first", "xaz", part_of_speech="noun")
    tiny_db.add_english_mapping("act", "xaz", part_of_speech="verb")
    statements = []
    tiny_db.conn.set_trace_callback(statements.append)
    try:
        content = tiny_db.export_markdown(tmp_path / "dictionary.md")
    finally:
        tiny_db.conn.set_trace_callback(None)
    assert len([sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]) <= 3
    assert "| `xaz` | first sense | noun,verb |" in content
    assert "| `test19` |" in content


def test_facade_keeps_context_note_preference(tiny_db):
    tiny_db.conn.execute("UPDATE roots SET meaning = 'probe' WHERE root = 'fatyih'")
    tiny_db.conn.commit()
    tiny_db.add_english_mapping("probe", "xaz", context_note="probe")
    tiny_db.add_english_mapping("probe", "fatyih")
    with Xenari(tiny_db.db_path, read_only=True) as x:
        assert x.lookup("probe")[0] == tiny_db.lookup("probe")[0] == "xaz"
        assert x.lookup("probe", part_of_speech="pronoun") == (None, None)


def test_read_only_connection_observes_committed_wal(tiny_db):
    tiny_db.conn.execute("PRAGMA journal_mode=WAL")
    tiny_db.conn.execute("INSERT INTO roots (root, meaning) VALUES ('zakglu', 'in WAL')")
    tiny_db.conn.commit()
    with XenariDB(tiny_db.db_path, read_only=True) as reader:
        assert reader.has_root("zakglu")
        with pytest.raises(sqlite3.OperationalError):
            reader.conn.execute("DELETE FROM roots")


@pytest.mark.parametrize("text", ["-5", "1.5", "5 + -2", "2.5 + 3", "I have 1.5 euros", "I have -5 euros"])
def test_unsupported_numeric_forms_do_not_change_value(xenari, text):
    rendered = xenari.speak(text)
    assert rendered.startswith("[untranslated:"), rendered
    assert text in rendered


def test_explicit_present_tense_option(run_cli):
    result = run_cli("speak", "I saw you", "--tense", "present")
    assert result.returncode == 0, result.stderr
    assert " sa " in result.stdout


def test_missing_runtime_check_is_a_clean_cli_failure(tmp_path, run_cli):
    result = run_cli("export-runtime", "--check", "--output", tmp_path / "missing.json")
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_gap_directory_input_is_a_clean_cli_failure(tmp_path, run_cli):
    result = run_cli("gaps", tmp_path)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_gap_phrases_do_not_bridge_filtered_names(xenari):
    harvester = GapHarvester(xenari)
    report = harvester.harvest_documents(
        [{"source": "script", "text": "flibbertigibbet Alice shimmerghost"}],
        phrase_min_count=1,
    )
    phrases = {item["key"] for item in report["buckets"]["phrase_gaps"]}
    assert "flibbertigibbet shimmerghost" not in phrases


@pytest.mark.parametrize("output", ["", "[unsupported: unknown construction]"])
def test_reports_do_not_label_missing_output_complete(output):
    report = build_translation_report(source="input", direction="english_to_xenari", output=output)
    assert report["status"] == "unsupported"


def test_report_distinguishes_partial_success_from_no_translation():
    report = build_translation_report(
        source="input", direction="english_to_xenari",
        output="ra mex ka neq ta zrent sa xo. [untranslated: missing clause]",
    )
    assert report["status"] == "partial"


def test_large_integer_round_trip(xenari):
    value = "9007199254740993"
    assert xenari.reverse(xenari.speak(value)) == value
