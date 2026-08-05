"""Additive, conservative sense-level part-of-speech canon tests."""

import json
import sqlite3

import pytest

from xenari.db import PARTS_OF_SPEECH, XenariDB, normalize_part_of_speech
from xenari.db.pos import infer_mapping_part_of_speech
from xenari.paths import COMMON_ENGLISH_POS_V2, CORE_VOCABULARY_POS
from xenari.runtime_tables import REVERSE_PREFERRED


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


def test_explicit_infinitive_mapping_is_a_high_confidence_verb():
    assert infer_mapping_part_of_speech(
        "to arrive", "fliq", "to arrive", "Core Vocabulary"
    ) == ("verb", "English key matches definition infinitive head")


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
    assert exported["toq"]["english_parts_of_speech"]["eye"] == "noun"

    audit = xenari.db.audit(limit=0)
    assert "POS schema present: yes" in audit
    assert "Invalid POS values: 0" in audit
    ok, doctor = xenari.doctor()
    assert ok
    assert "parts of speech: ok" in doctor


def test_core_vocabulary_pos_fixture_is_exact_and_exported(xenari):
    fixture = json.loads(CORE_VOCABULARY_POS.read_text(encoding="utf-8"))
    assert fixture["scope"]["category"] == "Core Vocabulary"

    exported = {row["root"]: row for row in json.loads(xenari.db.export_json())}
    reviewed = 0
    for part_of_speech, mappings in fixture["mappings"].items():
        assert part_of_speech in PARTS_OF_SPEECH
        for english_key, root in mappings:
            row = xenari.db.conn.execute(
                """SELECT r.category, e.part_of_speech
                   FROM english_map e JOIN roots r ON r.id = e.root_id
                   WHERE e.english_key = ? AND r.root = ?""",
                (english_key, root),
            ).fetchone()
            assert row is not None
            assert row["category"] == "Core Vocabulary"
            assert row["part_of_speech"] == part_of_speech
            assert exported[root]["english_parts_of_speech"][english_key] == part_of_speech
            reviewed += 1

    assert reviewed == 175


def test_common_english_pos_v2_fixture_is_complete_and_exported(xenari):
    fixture = json.loads(COMMON_ENGLISH_POS_V2.read_text(encoding="utf-8"))
    exported = {row["root"]: row for row in json.loads(xenari.db.export_json())}
    reviewed = 0
    tagged = 0
    deferred = 0

    for review in fixture["category_reviews"]:
        rows = xenari.db.conn.execute(
            """SELECT e.english_key, r.root, e.part_of_speech
               FROM english_map e JOIN roots r ON r.id = e.root_id
               WHERE r.category = ?
               ORDER BY e.english_key, r.root""",
            (review["category"],),
        ).fetchall()
        assert len(rows) == review["expected_mapping_count"]

        explicit = {
            (english_key, root): part_of_speech
            for english_key, root, part_of_speech in review.get("mappings", [])
        }
        explicit.update(
            {
                (english_key, root): part_of_speech
                for english_key, root, part_of_speech in review.get("exceptions", [])
            }
        )
        deferred_pairs = {
            (english_key, root)
            for english_key, root, _reason in review.get("deferred", [])
        }
        actual_pairs = {(row["english_key"], row["root"]) for row in rows}
        assert set(explicit).issubset(actual_pairs)
        assert deferred_pairs.issubset(actual_pairs)

        for row in rows:
            pair = (row["english_key"], row["root"])
            if pair in deferred_pairs:
                assert row["part_of_speech"] is None
                deferred += 1
                reviewed += 1
                continue
            expected = explicit.get(pair, review.get("default_part_of_speech"))
            assert expected in PARTS_OF_SPEECH
            assert row["part_of_speech"] == expected
            assert exported[row["root"]]["english_parts_of_speech"][row["english_key"]] == expected
            tagged += 1
            reviewed += 1

    assert reviewed == fixture["scope"]["mapping_count"] == 199
    assert tagged == fixture["scope"]["tagged_mapping_count"] == 153
    assert deferred == fixture["scope"]["deferred_mapping_count"] == 46
    assert fixture["collision_resolutions"] == [
        {
            "english_key": "solving",
            "root": "pyoquqab",
            "part_of_speech": "verb",
            "reason": "Retained because Python and browser phrase fixtures already assert this exact root and round trip.",
        }
    ]
    assert xenari.lookup("solving", part_of_speech="verb")[0] == "pyoquqab"

    expected_reverse_preferences = {
        "calar": ("decreasing", "verb"),
        "hevu": ("jammed", "verb"),
        "kloxi": ("inflated", "verb"),
        "sfupzhaq": ("momentarily", "adverb"),
        "shicey": ("increasing", "verb"),
        "sisolse": ("mimicking", "verb"),
        "trala": ("intended", "verb"),
        "verun": ("authored", "verb"),
        "xoqom": ("whirling", "verb"),
        "zeyor": ("hovers", "verb"),
        "zoqevel": ("constructed", "verb"),
        "zukaqop": ("disconnects", "verb"),
    }
    assert {
        root: (english_key, part_of_speech)
        for root, english_key, part_of_speech in fixture["reverse_preferences"]
    } == expected_reverse_preferences
    for root, (english_key, part_of_speech) in expected_reverse_preferences.items():
        assert REVERSE_PREFERRED[root] == english_key
        assert xenari.lookup(english_key, part_of_speech=part_of_speech)[0] == root
        assert xenari.translator._reverse_head_gloss(root) == english_key


def test_common_grammar_keys_do_not_resolve_through_compound_glosses(xenari):
    expected = {
        "to": "fa",
        "of": "po",
        "in": "na",
        "into": None,
        "through": "droqe",
        "has": "xrong",
        "have": "xrong",
        "own": "xrong",
        "do": "trong",
        "after": "vrem",
        "also": "pleng",
        "below": "srut",
        "my": "neq",
        "your": "mex",
    }

    for english_key, root in expected.items():
        resolved, _meaning = xenari.lookup(english_key)
        assert resolved == root


def test_pos_aware_lookup_preserves_homographic_ogden_senses(xenari):
    assert xenari.lookup("bite", part_of_speech="verb")[0] == "qruq'"
    assert xenari.lookup("bite", part_of_speech="noun")[0] == "krap"
    assert xenari.lookup("mine", part_of_speech="pronoun")[0] == "neq"
    assert xenari.lookup("mine", part_of_speech="noun")[0] == "puqu"


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
