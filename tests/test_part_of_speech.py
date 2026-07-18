"""Additive, conservative sense-level part-of-speech canon tests."""

import json
import sqlite3

import pytest

from xenari.db import PARTS_OF_SPEECH, XenariDB, normalize_part_of_speech


def _create_legacy_database(path, *, schema_version="legacy"):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE roots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            root TEXT UNIQUE NOT NULL,
            meaning TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Uncategorized',
            source TEXT,
            timestamp TEXT,
            notes TEXT
        );
        CREATE TABLE english_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            english_key TEXT NOT NULL,
            root_id INTEGER NOT NULL,
            context_note TEXT,
            FOREIGN KEY (root_id) REFERENCES roots(id) ON DELETE CASCADE,
            UNIQUE(english_key, root_id)
        );
        CREATE TABLE tool_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.execute(
        "INSERT INTO tool_meta VALUES ('schema_version', ?, '2026-01-01')",
        (schema_version,),
    )
    rows = [
        ("neq", "1st ordinal speaker", "Function Words & Grammar", "i"),
        ("ka", "subject marker", "Function Words & Grammar", "subject"),
        ("zrent", "love", "Mental & Abstract", "love"),
        ("xaz", "to test", "Tests", "test"),
        ("xoz", "ambiguous test concept", "Tests", "mystery"),
    ]
    for root, meaning, category, english_key in rows:
        cursor = conn.execute(
            "INSERT INTO roots (root, meaning, category) VALUES (?, ?, ?)",
            (root, meaning, category),
        )
        conn.execute(
            "INSERT INTO english_map (english_key, root_id) VALUES (?, ?)",
            (english_key, cursor.lastrowid),
        )
    conn.commit()
    conn.close()


def _mapping_pos(db, english_key, root):
    row = db.conn.execute(
        """SELECT e.part_of_speech
           FROM english_map e JOIN roots r ON r.id = e.root_id
           WHERE e.english_key = ? AND r.root = ?""",
        (english_key, root),
    ).fetchone()
    return row[0] if row else None


def test_read_only_legacy_database_exposes_unknown_pos_without_mutating(tmp_path):
    path = tmp_path / "legacy.db"
    _create_legacy_database(path)

    with XenariDB(path, read_only=True) as db:
        assert db.lookup_root("neq")["parts_of_speech"] == []
        exported = json.loads(db.export_json())
        assert "english_parts_of_speech" not in exported[0]
        report = db.part_of_speech_report()
        assert report["schema_present"] is False
        assert report["unknown"] == 5
        assert "POS schema present: no" in db.audit(limit=0)

    conn = sqlite3.connect(path)
    assert "part_of_speech" not in {
        row[1] for row in conn.execute("PRAGMA table_info(english_map)")
    }
    conn.close()


def test_writable_open_migrates_and_backfill_only_sets_high_confidence_senses(tmp_path):
    path = tmp_path / "legacy.db"
    _create_legacy_database(path)

    with XenariDB(path, read_only=False) as db:
        assert db._has_part_of_speech_column()
        preview = db.backfill_parts_of_speech()
        assert preview["applied"] is False
        assert preview["proposal_count"] == 4
        assert db.part_of_speech_report()["annotated"] == 0

        applied = db.backfill_parts_of_speech(apply=True)
        assert applied["applied"] is True
        assert applied["coverage"]["annotated"] == 4
        assert applied["coverage"]["unknown"] == 1
        assert _mapping_pos(db, "i", "neq") == "pronoun"
        assert _mapping_pos(db, "subject", "ka") == "particle"
        assert _mapping_pos(db, "love", "zrent") == "verb"
        assert _mapping_pos(db, "test", "xaz") == "verb"
        assert _mapping_pos(db, "mystery", "xoz") is None
        assert db.conn.execute(
            "SELECT value FROM tool_meta WHERE key = 'schema_version'"
        ).fetchone()[0] == "2026-07-18.2"
        assert db.conn.execute(
            "SELECT value FROM tool_meta WHERE key = 'pos_backfill_version'"
        ).fetchone()[0] == "2026-07-18.3"

        with pytest.raises(sqlite3.IntegrityError):
            db.conn.execute(
                """UPDATE english_map SET part_of_speech = 'definitely-not-pos'
                   WHERE english_key = 'mystery'"""
            )

    assert list(tmp_path.glob("legacy.db.*.schema-pos-v2.bak"))


def test_pos_is_mapping_level_and_preserves_polysemy(writable_db):
    db = writable_db
    assert normalize_part_of_speech("proper noun") == "proper_noun"
    with pytest.raises(ValueError):
        normalize_part_of_speech("banana")

    assert db.set_mapping_part_of_speech("eye", "toq", "noun")
    assert db.set_mapping_part_of_speech("see", "toq", "verb")
    assert db.parts_of_speech_for_root("toq") == ["noun", "verb"]
    verb_senses = db.mappings_by_part_of_speech("verb", limit=10_000)
    assert any(row["english_key"] == "see" and row["root"] == "toq" for row in verb_senses)
    assert not db.set_mapping_part_of_speech("missing", "toq", "noun")

    ok, messages = db.add_root(
        "temporary-pos-root",
        "xaz",
        "temporary noun",
        category="Tests",
        part_of_speech="noun",
    )
    assert ok, messages
    assert _mapping_pos(db, "temporary-pos-root", "xaz") == "noun"

    ok, messages = db.add_root(
        "invalid-pos-root",
        "xoz",
        "temporary concept",
        category="Tests",
        part_of_speech="banana",
    )
    assert not ok
    assert "unknown part of speech" in messages[0]


def test_canon_pos_is_exposed_by_queries_export_audit_and_doctor(xenari):
    report = xenari.db.part_of_speech_report()
    assert report["schema_present"] is True
    assert report["annotated"] > 0
    assert report["unknown"] > 0
    assert not report["invalid"]
    assert set(report["counts"]).issubset(PARTS_OF_SPEECH)

    assert _mapping_pos(xenari.db, "subject", "ka") == "particle"
    assert _mapping_pos(xenari.db, "one", "ca") == "numeral"
    assert _mapping_pos(xenari.db, "love", "zrent") == "verb"
    assert "verb" in xenari.db.lookup_root("toq")["parts_of_speech"]
    assert _mapping_pos(xenari.db, "ear", "cromq") == "noun"
    assert _mapping_pos(xenari.db, "hear", "cromq") == "verb"
    assert xenari.db.lookup_root("cromq")["parts_of_speech"] == ["noun", "verb"]
    assert _mapping_pos(xenari.db, "disturb", "xi") is None
    assert _mapping_pos(xenari.db, "module", "ta") is None

    exported = {row["root"]: row for row in json.loads(xenari.db.export_json())}
    assert exported["toq"]["english_parts_of_speech"]["see"] == "verb"
    assert "eye" not in exported["toq"]["english_parts_of_speech"]

    audit = xenari.db.audit(limit=0)
    assert "POS schema present: yes" in audit
    assert "Invalid POS values: 0" in audit
    ok, doctor = xenari.doctor()
    assert ok
    assert "parts of speech: ok" in doctor


def test_same_schema_open_is_stable_and_future_schema_is_rejected(tmp_path):
    path = tmp_path / "stable.db"
    _create_legacy_database(path)
    with XenariDB(path, read_only=False) as db:
        before = db.conn.execute(
            "SELECT updated_at FROM tool_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
    with XenariDB(path, read_only=False) as db:
        after = db.conn.execute(
            "SELECT updated_at FROM tool_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
    assert after == before

    future = tmp_path / "future.db"
    _create_legacy_database(future, schema_version="2099-01-01.1")
    with pytest.raises(RuntimeError, match="newer than this Xenari build"):
        XenariDB(future, read_only=False)
