"""Reviewed sense-level part-of-speech and reversibility canon tests."""

import hashlib
import json
import sqlite3
from collections import Counter

import pytest

from xenari.db import PARTS_OF_SPEECH, XenariDB, normalize_part_of_speech
from xenari.db.pos import infer_mapping_part_of_speech
from xenari.grammar import DEFAULT_GRAMMAR
from xenari.paths import (
    CANON_DB,
    COMMON_ENGLISH_POS_V2,
    COMMON_ENGLISH_POS_V3,
    COMMON_ENGLISH_POS_V4,
    CORE_VOCABULARY_POS,
)
from xenari.runtime_tables import (
    FORWARD_PREFERRED,
    LOOKUP_PREFERRED_BY_PART_OF_SPEECH,
    REVERSE_PLURAL_NOUN_ROOTS,
    REVERSE_PREFERRED,
    REVERSE_PREFERRED_BY_PART_OF_SPEECH,
    REVERSE_VERB_INFLECTIONS,
    TRANSLATION_PREFERRED_BY_PART_OF_SPEECH,
)


def _stable_json_sha256(value):
    source = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(source.encode()).hexdigest()


def _pair_sha256(pairs):
    source = "\n".join(f"{english_key}\t{root}" for english_key, root in sorted(pairs))
    return hashlib.sha256(source.encode()).hexdigest()


def _assert_terminal_decision_applied(db, decision):
    english_key = decision["english_key"]
    root = decision["root"]
    action = decision["action"]
    if action == "tag":
        assert _mapping_pos(db, english_key, root) == decision["part_of_speech"]
        return

    assert _mapping_pos(db, english_key, root) is None
    assert db.conn.execute(
        """SELECT 1 FROM english_map e JOIN roots r ON r.id = e.root_id
           WHERE e.english_key = ? AND r.root = ?""",
        (english_key, root),
    ).fetchone() is None
    if action == "replace":
        assert (
            _mapping_pos(db, decision["replacement_english_key"], root)
            == decision["part_of_speech"]
        )
    else:
        assert action == "delete"


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


def _insert_unknown_mapping(db, english_key, root, meaning=None):
    cursor = db.conn.execute(
        """INSERT INTO roots (root, meaning, category)
           VALUES (?, ?, 'Tests')""",
        (root, meaning or english_key),
    )
    db.conn.execute(
        """INSERT INTO english_map
           (english_key, root_id, context_note, part_of_speech)
           VALUES (?, ?, NULL, NULL)""",
        (english_key, cursor.lastrowid),
    )
    db.conn.commit()


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


def test_pos_batch_is_atomic_and_creates_one_backup(writable_db, tmp_path):
    _insert_unknown_mapping(writable_db, "batch-humble", "curhum")
    _insert_unknown_mapping(writable_db, "batch-yak", "curyak")
    report = writable_db.set_mapping_parts_of_speech(
        [
            ("batch-humble", "curhum", "adjective"),
            ("batch-yak", "curyak", "noun"),
        ],
        operation="test-pos-batch",
    )
    assert report["mapping_count"] == 2
    assert report["applied"] == 2
    assert report["unchanged"] == 0
    assert report["backup"] is not None
    assert len(list(tmp_path.glob("xenari.db.*.test-pos-batch.bak"))) == 1
    assert _mapping_pos(writable_db, "batch-humble", "curhum") == "adjective"
    assert _mapping_pos(writable_db, "batch-yak", "curyak") == "noun"

    with pytest.raises(ValueError, match="duplicate POS batch mapping"):
        writable_db.set_mapping_parts_of_speech(
            [
                ("batch-humble", "curhum", "adjective"),
                ("batch-humble", "curhum", "adjective"),
            ]
        )
    with pytest.raises(ValueError, match="conflicting POS batch mapping"):
        writable_db.set_mapping_parts_of_speech(
            [("batch-humble", "curhum", "verb")]
        )
    assert _mapping_pos(writable_db, "batch-humble", "curhum") == "adjective"


def test_mapping_curation_batch_applies_mixed_actions_atomically(
    writable_db, tmp_path
):
    db = writable_db
    for english_key, root, meaning in [
        ("curation-humble", "curhum", "humble"),
        ("curation-yak", "curyak", "yak; talk endlessly"),
        ("curation-held", "curheld", "obsolete held fragment"),
        ("curation-map", "curmap", "shadow map"),
        ("curation-map", "curres", "resonance map"),
        ("curation-weighing", "curstone", "weighing stone"),
        ("curation-star", "curchart", "star chart"),
    ]:
        _insert_unknown_mapping(db, english_key, root, meaning)
    roots_before = db.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0]
    mappings_before = db.conn.execute(
        "SELECT COUNT(*) FROM english_map"
    ).fetchone()[0]
    db.conn.execute(
        """UPDATE english_map SET context_note = 'preserve me'
           WHERE english_key = 'curation-map'
             AND root_id = (SELECT id FROM roots WHERE root = 'curmap')"""
    )
    db.conn.commit()

    report = db.apply_mapping_curation_batch(
        [
            {
                "action": "tag_primary",
                "english_key": "curation-humble",
                "root": "curhum",
                "pos": "adjective",
            },
            {
                "action": "tag",
                "english_key": "curation-yak",
                "root": "curyak",
                "part_of_speech": "noun",
            },
            {
                "action": "delete_mapping",
                "english_key": "curation-held",
                "root": "curheld",
            },
            {
                "action": "rename_and_tag",
                "english_key": "curation-map",
                "root": "curmap",
                "replacement_english_key": "curation shadow map",
                "pos": "noun",
            },
            {
                "action": "normalize",
                "english_key": "curation-map",
                "root": "curres",
                "new_english_key": "curation resonance map",
                "part_of_speech": "noun",
            },
            {
                "action": "refine_mapping",
                "english_key": "curation-weighing",
                "root": "curstone",
                "new_english_key": "curation weighing stone",
                "part_of_speech": "noun",
            },
            {
                "action": "replace",
                "english_key": "curation-star",
                "root": "curchart",
                "new_english_key": "curation star chart",
                "replacement_pos": "noun",
            },
            {
                "action": "add_split_mapping",
                "source_english_key": "curation-yak",
                "new_english_key": "curation talk endlessly",
                "root": "curyak",
                "part_of_speech": "verb",
                "context_note": "split from the old mixed yak gloss",
            },
        ],
        operation="atomic-curation",
    )

    assert report == {
        "action_count": 8,
        "applied": 8,
        "changed_rows": 8,
        "counts": {"delete": 1, "rename": 4, "split": 1, "tag": 2},
        "backup": report["backup"],
    }
    assert report["backup"] is not None
    assert len(list(tmp_path.glob("xenari.db.*.atomic-curation.bak"))) == 1
    assert _mapping_pos(db, "curation-humble", "curhum") == "adjective"
    assert _mapping_pos(db, "curation-yak", "curyak") == "noun"
    assert _mapping_pos(db, "curation talk endlessly", "curyak") == "verb"
    assert _mapping_pos(db, "curation-held", "curheld") is None
    assert db.conn.execute(
        """SELECT 1 FROM english_map e JOIN roots r ON r.id = e.root_id
           WHERE e.english_key = 'curation-held' AND r.root = 'curheld'"""
    ).fetchone() is None
    renamed = db.conn.execute(
        """SELECT e.part_of_speech, e.context_note
           FROM english_map e JOIN roots r ON r.id = e.root_id
           WHERE e.english_key = 'curation shadow map' AND r.root = 'curmap'"""
    ).fetchone()
    assert tuple(renamed) == ("noun", "preserve me")
    assert _mapping_pos(db, "curation resonance map", "curres") == "noun"
    assert _mapping_pos(db, "curation weighing stone", "curstone") == "noun"
    assert _mapping_pos(db, "curation star chart", "curchart") == "noun"
    assert db.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0] == roots_before
    assert (
        db.conn.execute("SELECT COUNT(*) FROM english_map").fetchone()[0]
        == mappings_before
    )


def test_mapping_curation_batch_rejects_stale_duplicates_and_conflicts(
    writable_db, tmp_path
):
    db = writable_db
    _insert_unknown_mapping(db, "conflict-humble", "confhum")
    _insert_unknown_mapping(db, "conflict-star", "confstar", "star chart")
    root_id = db.conn.execute(
        "SELECT id FROM roots WHERE root = 'confstar'"
    ).fetchone()[0]
    db.conn.execute(
        """INSERT INTO english_map
           (english_key, root_id, context_note, part_of_speech)
           VALUES ('conflict-chart', ?, NULL, 'noun')""",
        (root_id,),
    )
    db.conn.commit()
    with pytest.raises(ValueError, match="duplicate mapping curation source"):
        db.apply_mapping_curation_batch(
            [
                {
                    "action": "tag",
                    "english_key": "conflict-humble",
                    "root": "confhum",
                    "part_of_speech": "adjective",
                },
                {
                    "action": "delete",
                    "english_key": "conflict-humble",
                    "root": "confhum",
                },
            ]
        )
    with pytest.raises(ValueError, match="source mismatch"):
        db.apply_mapping_curation_batch(
            [
                {
                    "action": "tag",
                    "english_key": "conflict-humble",
                    "root": "confhum",
                    "part_of_speech": "adjective",
                    "expected_part_of_speech": "noun",
                }
            ]
        )
    with pytest.raises(ValueError, match="target already exists"):
        db.apply_mapping_curation_batch(
            [
                {
                    "action": "refine",
                    "english_key": "conflict-star",
                    "root": "confstar",
                    "new_english_key": "conflict-chart",
                    "part_of_speech": "noun",
                }
            ]
        )
    with pytest.raises(ValueError, match="missing mapping curation source"):
        db.apply_mapping_curation_batch(
            [
                {
                    "action": "add_split_mapping",
                    "source_english_key": "missing source",
                    "new_english_key": "talk endlessly",
                    "root": "confhum",
                    "part_of_speech": "verb",
                }
            ]
        )

    assert _mapping_pos(db, "conflict-humble", "confhum") is None
    assert not list(tmp_path.glob("xenari.db.*.mapping-curation-batch.bak"))


def test_mapping_curation_batch_rolls_back_after_a_sqlite_failure(
    writable_db, tmp_path
):
    db = writable_db
    _insert_unknown_mapping(db, "rollback-humble", "rollhum")
    _insert_unknown_mapping(db, "rollback-map", "rollmap", "shadow map")
    db.conn.executescript(
        """
        CREATE TRIGGER force_curation_failure
        BEFORE UPDATE OF english_key ON english_map
        WHEN NEW.english_key = 'rollback shadow map'
        BEGIN
            SELECT RAISE(ABORT, 'forced curation failure');
        END;
        """
    )
    db.conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="forced curation failure"):
        db.apply_mapping_curation_batch(
            [
                {
                    "action": "tag",
                    "english_key": "rollback-humble",
                    "root": "rollhum",
                    "part_of_speech": "adjective",
                },
                {
                    "action": "rename_mapping_and_tag",
                    "english_key": "rollback-map",
                    "root": "rollmap",
                    "new_english_key": "rollback shadow map",
                    "part_of_speech": "noun",
                },
            ],
            operation="forced-curation-failure",
        )

    assert _mapping_pos(db, "rollback-humble", "rollhum") is None
    assert db.conn.execute(
        """SELECT 1 FROM english_map e JOIN roots r ON r.id = e.root_id
           WHERE e.english_key = 'rollback-map' AND r.root = 'rollmap'"""
    ).fetchone() is not None
    assert db.conn.execute(
        """SELECT 1 FROM english_map e JOIN roots r ON r.id = e.root_id
           WHERE e.english_key = 'rollback shadow map' AND r.root = 'rollmap'"""
    ).fetchone() is None
    assert len(list(tmp_path.glob("xenari.db.*.forced-curation-failure.bak"))) == 1


def test_explicit_infinitive_mapping_is_a_high_confidence_verb():
    assert infer_mapping_part_of_speech(
        "to arrive", "fliq", "to arrive", "Core Vocabulary"
    ) == ("verb", "English key matches definition infinitive head")


def test_canon_pos_is_exposed_by_queries_export_audit_and_doctor(xenari):
    report = xenari.db.part_of_speech_report()
    assert report["schema_present"] is True
    assert report["annotated"] > 0
    assert report["unknown"] == 0
    assert not report["invalid"]
    assert set(report["counts"]).issubset(PARTS_OF_SPEECH)

    assert _mapping_pos(xenari.db, "subject", "ka") == "particle"
    assert _mapping_pos(xenari.db, "one", "ca") == "numeral"
    assert _mapping_pos(xenari.db, "love", "zrent") == "verb"
    assert "verb" in xenari.db.lookup_root("toq")["parts_of_speech"]
    assert _mapping_pos(xenari.db, "ear", "cromq") == "noun"
    assert _mapping_pos(xenari.db, "hear", "cromq") == "verb"
    assert xenari.db.lookup_root("cromq")["parts_of_speech"] == ["noun", "verb"]
    assert _mapping_pos(xenari.db, "disturb", "xi") == "verb"
    assert _mapping_pos(xenari.db, "module", "ta") == "noun"

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


def test_common_english_pos_v2_is_immutable_history_superseded_by_v4(xenari):
    fixture = json.loads(COMMON_ENGLISH_POS_V2.read_text(encoding="utf-8"))
    v4 = json.loads(COMMON_ENGLISH_POS_V4.read_text(encoding="utf-8"))
    terminal = {
        (decision["english_key"], decision["root"]): decision
        for decision in v4["decisions"]
    }

    assert fixture["schema"] == "xenari.common-english-pos.v2"
    assert fixture["scope"] == {
        "selection": (
            "Complete mapping-level review of ten legacy categories whose names "
            "encode intended English POS, including explicit corrections where "
            "the imported category was wrong."
        ),
        "mapping_count": 199,
        "tagged_mapping_count": 153,
        "newly_tagged_count": 140,
        "deferred_mapping_count": 46,
    }

    categories = [review["category"] for review in fixture["category_reviews"]]
    assert len(categories) == len(set(categories)) == 10
    assert sum(
        review["expected_mapping_count"]
        for review in fixture["category_reviews"]
    ) == fixture["scope"]["mapping_count"]

    tagged = 0
    deferred_pairs = set()
    for review in fixture["category_reviews"]:
        explicit = [
            *review.get("mappings", []),
            *review.get("exceptions", []),
        ]
        deferred = review.get("deferred", [])
        assert len(explicit) + len(deferred) <= review["expected_mapping_count"]
        tagged += review["expected_mapping_count"] - len(deferred)

        for english_key, root, part_of_speech in explicit:
            assert part_of_speech in PARTS_OF_SPEECH
            assert _mapping_pos(xenari.db, english_key, root) == part_of_speech
        for english_key, root, reason in deferred:
            pair = (english_key, root)
            assert reason
            assert pair not in deferred_pairs
            deferred_pairs.add(pair)
            decision = terminal[pair]
            assert decision["expected_part_of_speech"] is None
            _assert_terminal_decision_applied(xenari.db, decision)

    assert tagged == fixture["scope"]["tagged_mapping_count"]
    assert len(deferred_pairs) == fixture["scope"]["deferred_mapping_count"]
    assert {terminal[pair]["action"] for pair in deferred_pairs} == {"tag"}

    for resolution in fixture["collision_resolutions"]:
        assert _mapping_pos(
            xenari.db,
            resolution["english_key"],
            resolution["root"],
        ) == resolution["part_of_speech"]
    for root, english_key, part_of_speech in fixture["reverse_preferences"]:
        assert _mapping_pos(xenari.db, english_key, root) == part_of_speech


def test_common_english_pos_v3_is_immutable_history_superseded_by_v4(xenari):
    fixture = json.loads(COMMON_ENGLISH_POS_V3.read_text(encoding="utf-8"))
    v4 = json.loads(COMMON_ENGLISH_POS_V4.read_text(encoding="utf-8"))
    terminal = {
        (decision["english_key"], decision["root"]): decision
        for decision in v4["decisions"]
    }

    assert fixture["schema"] == "xenari.common-english-pos.v3"
    assert fixture["scope"] == {
        "selection": (
            "Every previously untyped, structurally bijective mapping in the "
            "nine explicit noun, adjective, and verb legacy categories was "
            "reviewed at sense level."
        ),
        "mapping_count": 1028,
        "newly_tagged_count": 1000,
        "deferred_mapping_count": 28,
        "selection_sha256": (
            "3527103e7bc1be0b7b84fb8b50bc17148234eccd2d9631b24726083a9eceb5f0"
        ),
    }
    assert set(fixture["selection"]["categories"]) == set(
        fixture["default_parts_of_speech"]
    )
    assert sum(fixture["expected_tagged_by_category"].values()) == 1000
    assert sum(fixture["expected_tagged_by_part_of_speech"].values()) == 1000

    preexisting = {
        (english_key, root): part_of_speech
        for english_key, root, part_of_speech in fixture["preexisting_mappings"]
    }
    overrides = {
        (english_key, root): part_of_speech
        for english_key, root, part_of_speech in fixture["overrides"]
    }
    deferred = {
        (english_key, root): reason
        for english_key, root, reason in fixture["deferred"]
    }
    assert not set(preexisting) & set(deferred)
    assert not set(overrides) & set(deferred)
    assert len(deferred) == fixture["scope"]["deferred_mapping_count"]

    for mappings in (preexisting, overrides):
        for (english_key, root), part_of_speech in mappings.items():
            assert part_of_speech in PARTS_OF_SPEECH
            assert _mapping_pos(xenari.db, english_key, root) == part_of_speech
    for pair, reason in deferred.items():
        assert reason
        decision = terminal[pair]
        assert decision["expected_part_of_speech"] is None
        _assert_terminal_decision_applied(xenari.db, decision)
    assert {terminal[pair]["action"] for pair in deferred} == {"tag"}

    for english_key, mapping_root, preferred_root in fixture["forward_preferences"]:
        assert _mapping_pos(xenari.db, english_key, mapping_root) == "verb"
        assert (
            LOOKUP_PREFERRED_BY_PART_OF_SPEECH["verb"].get(
                english_key, mapping_root
            )
            == mapping_root
        )
        assert (
            TRANSLATION_PREFERRED_BY_PART_OF_SPEECH["verb"][english_key]
            == preferred_root
        )
        assert xenari.lookup(english_key, part_of_speech="verb")[0] == mapping_root
        assert xenari._known_verb_root(english_key) == preferred_root


def test_common_english_pos_v4_has_exact_terminal_provenance():
    fixture = json.loads(COMMON_ENGLISH_POS_V4.read_text(encoding="utf-8"))
    decisions = fixture["decisions"]
    additions = fixture["add_mappings"]
    preferences = fixture["preferences"]

    assert fixture["schema"] == "xenari.common-english-pos.v4"
    assert fixture["source"] == {
        "canon_commit": "8a02ca2f6737015696d16886f80d34dacafe0f28",
        "database_sha256": (
            "17f42ee9d93d0d96b55210d20e88c4819c483854a69ad902cfb2e7e20282a5eb"
        ),
        "proposal_file_sha256": {
            "curated_reversibility_aliases": (
                "5abadd5b6aadf28059d6975ef233ab661d9b878dc9edc79bb4d2397f9a65de93"
            ),
            "decision_corrections": (
                "5424a78e1abf290ed5c8d3a552371b340f939290ae67ff118cf62112bb6a3726"
            ),
            "explicit": (
                "ab5b22dfae93449e9713ebe30507a0d9cf2c5211e86234b0772d0d046bdc066d"
            ),
            "general": (
                "21c9400091436cddac5602d485ed5bbc871914b303fd3ff31dea37810761bcbd"
            ),
            "legacy_selection_additions": (
                "40d304a1c04c6f54cc0cd03171089a5aeb46262d585608d5907518e47cb44576"
            ),
            "legacy_selection_baseline": (
                "973d7e819385157b42fd13f2f4e0cb9ca5064c9636df270505ad3c0c9cda3509"
            ),
            "runtime_additions_review": (
                "07a0bf4e5d8d388b986f03433a6431252cf542e52ef9e04079f2bc459bfb7e1a"
            ),
            "roundtrip_repair_aliases": (
                "78f42a0db1f2cb782f7323d2b3ac4dac7ac4d4d644b0eb6c787cdca7086fa668"
            ),
            "reverse_morphology_residuals": (
                "b7f7f5a6815d07567a747e80a051ac56d36c85d7e0fcea2daf8154c16d4ca382"
            ),
            "reverse_plural_np_audit": (
                "0784225288c54a343a310b063b02b3a4a27710cea596a5d1b46b3e7fc0648664"
            ),
            "reverse_role_derivation": (
                "63a977b5ee13e2a3ea35f5b850e5bcc7c467c049808b3785f8fbeee029aca253"
            ),
            "reverse_role_preferences": (
                "31aeaab1b4ce2c5fd63e83e526fb2ae018db36156bb664bb57a1db47e712bdb3"
            ),
            "reverse_verb_inflections": (
                "868dcb598ec0484a1679478a4cc9bb1e7d3d0c543dd92ae7f4daf7121aa32858"
            ),
            "semantic": (
                "33d6c23118b0e5a6038cad6680f89ebc21017ff8dbe82dee1740abf579f703e1"
            ),
        },
        "unknown_baseline_file_sha256": (
            "cae110f298bd42b9ba5adf2201f3c2b48dfff2d9e14623830f43bf32171e6c4f"
        ),
    }
    assert fixture["scope"] == {
        "addition_count": 341,
        "addition_counts": {
            "explicit": 2,
            "legacy_selection_repair": 26,
            "reversibility": 132,
            "roundtrip_repair": 48,
            "runtime": 133,
        },
        "decision_counts": {"delete": 510, "replace": 347, "tag": 8468},
        "description": (
            "Every mapping that was still untyped after common-English POS v3; "
            "each source pair has exactly one terminal tag, replace, or delete "
            "decision."
        ),
        "source_mapping_count": 9325,
        "source_pair_sha256": (
            "b7dd28bae4311620a83ddedb5fd68a4b227ce9b69ef7cebc5ec8787af2636887"
        ),
        "terminal_decision_sha256": (
            "f3148627447266ea75f9e2af1a220bb7c60cc5863e5e324c5880c7533a96a6aa"
        ),
    }

    source_pairs = [
        (decision["english_key"], decision["root"])
        for decision in decisions
    ]
    assert len(source_pairs) == len(set(source_pairs)) == 9325
    assert _pair_sha256(source_pairs) == fixture["scope"]["source_pair_sha256"]
    assert Counter(decision["action"] for decision in decisions) == Counter(
        fixture["scope"]["decision_counts"]
    )
    assert all(decision["expected_part_of_speech"] is None for decision in decisions)

    terminal_projection = [
        {
            "action": decision["action"],
            "english_key": decision["english_key"],
            "part_of_speech": decision.get("part_of_speech"),
            "replacement_english_key": decision.get("replacement_english_key"),
            "root": decision["root"],
            "stream": decision["stream"],
        }
        for decision in decisions
    ]
    assert _stable_json_sha256(terminal_projection) == fixture["scope"][
        "terminal_decision_sha256"
    ]

    addition_pairs = [
        (addition["new_english_key"], addition["root"])
        for addition in additions
    ]
    assert len(addition_pairs) == len(set(addition_pairs)) == 341
    assert Counter(addition["stream"] for addition in additions) == Counter(
        fixture["scope"]["addition_counts"]
    )
    assert {addition["action"] for addition in additions} == {"add_mapping"}

    hashes = fixture["hashes"]
    assert _stable_json_sha256(decisions) == hashes["decisions_sha256"]
    assert _stable_json_sha256(additions) == hashes["add_mappings_sha256"]
    assert _stable_json_sha256(preferences) == hashes["preferences_sha256"]
    reverse_roles_json = (
        json.dumps(
            preferences["reverse"]["preferred_by_part_of_speech"],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    assert hashlib.sha256(reverse_roles_json.encode()).hexdigest() == hashes[
        "reverse_role_preferences_sha256"
    ]
    plural_root_lines = "".join(
        f"{root}\n" for root in preferences["reverse"]["plural_noun_roots"]
    )
    assert hashlib.sha256(plural_root_lines.encode()).hexdigest() == hashes[
        "reverse_plural_np_root_lines_sha256"
    ]
    verb_inflections = preferences["reverse"]["verb_inflections"]
    verb_inflections_json = (
        json.dumps(
            verb_inflections,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    assert hashlib.sha256(verb_inflections_json.encode()).hexdigest() == hashes[
        "reverse_verb_inflections_sha256"
    ]
    assert _stable_json_sha256(
        {"records": decisions, "add_mappings": additions}
    ) == hashes["actions_sha256"]
    assert hashlib.sha256(CANON_DB.read_bytes()).hexdigest() == hashes[
        "result_database_sha256"
    ]


def test_common_english_pos_v4_canon_preferences_and_roundtrips_are_complete(
    xenari,
):
    fixture = json.loads(COMMON_ENGLISH_POS_V4.read_text(encoding="utf-8"))
    verification = fixture["verification"]
    forward = fixture["preferences"]["forward"]
    reverse_preferences = fixture["preferences"]["reverse"]
    reverse = reverse_preferences["preferred"]
    reverse_roles = reverse_preferences["preferred_by_part_of_speech"]
    plural_noun_roots = set(reverse_preferences["plural_noun_roots"])
    verb_inflections = reverse_preferences["verb_inflections"]
    rows = xenari.db.conn.execute(
        """SELECT e.english_key, r.root, e.part_of_speech
           FROM english_map e JOIN roots r ON r.id = e.root_id"""
    ).fetchall()
    mappings = {
        (row["english_key"], row["root"]): row["part_of_speech"] for row in rows
    }
    roots_by_key = {}
    roots_by_key_and_pos = {}
    for english_key, root in mappings:
        part_of_speech = mappings[(english_key, root)]
        roots_by_key.setdefault(english_key, set()).add(root)
        roots_by_key_and_pos.setdefault((english_key, part_of_speech), set()).add(
            root
        )

    assert len(rows) == len(mappings) == verification["mapping_count"] == 11630
    assert all(part_of_speech in PARTS_OF_SPEECH for part_of_speech in mappings.values())
    assert xenari.db.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0] == (
        verification["root_count"]
    )
    assert verification["unknown_part_of_speech"] == 0
    assert verification["invalid_part_of_speech"] == 0
    assert verification["duplicate_mapping_pairs"] == 0
    assert verification["atomic_batch_action_count"] == 9325 + 341
    assert verification["atomic_batch_changed_rows"] == 9325 + 341
    assert verification["runtime_aliases_pending"] == 0
    assert verification["unmatched_roots"] == 0
    assert verification["reverse_role_group_count"] == 10061
    assert verification["reverse_plural_np_root_count"] == 853
    assert verification["reverse_verb_inflection_root_count"] == 2388
    assert set(verification["validation_error_counts"].values()) == {0}

    for decision in fixture["decisions"]:
        pair = (decision["english_key"], decision["root"])
        if decision["action"] == "tag":
            assert mappings[pair] == decision["part_of_speech"]
        else:
            assert pair not in mappings
            if decision["action"] == "replace":
                replacement = (decision["replacement_english_key"], decision["root"])
                assert mappings[replacement] == decision["part_of_speech"]
            else:
                assert decision["action"] == "delete"
    for addition in fixture["add_mappings"]:
        pair = (addition["new_english_key"], addition["root"])
        assert mappings[pair] == addition["part_of_speech"]

    colliding_keys = {
        english_key for english_key, roots in roots_by_key.items() if len(roots) > 1
    }
    same_pos_collisions = {
        pair for pair, roots in roots_by_key_and_pos.items() if len(roots) > 1
    }
    assert len(roots_by_key) == verification["distinct_english_keys"]
    assert len(colliding_keys) == verification["colliding_english_keys"]
    assert len(same_pos_collisions) == verification[
        "same_key_same_pos_collision_groups"
    ]

    default_preferences = forward["preferred"]
    lookup_preferences = forward["lookup_preferred_by_part_of_speech"]
    translation_preferences = forward[
        "translation_preferred_by_part_of_speech"
    ]
    assert dict(FORWARD_PREFERRED) == default_preferences
    assert {
        part_of_speech: dict(preferences)
        for part_of_speech, preferences in LOOKUP_PREFERRED_BY_PART_OF_SPEECH.items()
    } == lookup_preferences
    assert {
        part_of_speech: dict(preferences)
        for part_of_speech, preferences in (
            TRANSLATION_PREFERRED_BY_PART_OF_SPEECH.items()
        )
    } == translation_preferences
    assert dict(REVERSE_PREFERRED) == reverse
    assert {
        part_of_speech: dict(preferences)
        for part_of_speech, preferences in (
            REVERSE_PREFERRED_BY_PART_OF_SPEECH.items()
        )
    } == reverse_roles
    assert set(REVERSE_PLURAL_NOUN_ROOTS) == plural_noun_roots
    assert {
        root: dict(forms) for root, forms in REVERSE_VERB_INFLECTIONS.items()
    } == verb_inflections

    canonical_role_groups = {
        (part_of_speech, root)
        for (english_key, root), part_of_speech in mappings.items()
    }
    fixture_role_groups = {
        (part_of_speech, root)
        for part_of_speech, preferences in reverse_roles.items()
        for root in preferences
    }
    assert len(fixture_role_groups) == verification["reverse_role_group_count"]
    assert fixture_role_groups == canonical_role_groups
    assert set(reverse_roles) == PARTS_OF_SPEECH
    for part_of_speech, preferences in reverse_roles.items():
        for root, surface in preferences.items():
            assert surface == " ".join(surface.strip().lower().split())
            if part_of_speech != "verb":
                assert mappings[(surface, root)] == part_of_speech

    noun_like_roots = {
        root
        for part_of_speech, root in canonical_role_groups
        if part_of_speech in {"noun", "proper_noun"}
    }
    assert len(plural_noun_roots) == verification["reverse_plural_np_root_count"]
    assert plural_noun_roots <= noun_like_roots
    assert {
        "anmqu", "boze", "clerzdodrec", "flez", "saso", "staszmun",
        "xulm", "xuqha", "zbur", "zgagqxofvnon", "zifrelk",
    } <= plural_noun_roots
    assert {"fuvlal", "kreng", "qed", "sistfonh", "slozlus"}.isdisjoint(
        plural_noun_roots
    )
    assert reverse_roles["verb"]["tyequga"] == "rustle"
    assert reverse_roles["verb"]["hakar"] == "be born"
    assert reverse_roles["verb"]["xroqmaq'vi"] == "actively moderate"
    assert set(verb_inflections) == set(reverse_roles["verb"])
    assert all(
        set(forms) == {"past", "third_person"}
        and all(
            value == " ".join(value.strip().lower().split())
            for value in forms.values()
        )
        for forms in verb_inflections.values()
    )
    assert verb_inflections["tyequga"] == {
        "past": "rustled",
        "third_person": "rustles",
    }
    assert verb_inflections["clitqlap"]["past"] == "lay"
    assert verb_inflections["tasmqvofl"]["past"] == "lied"
    assert verb_inflections["slismunxat"]["third_person"] == "whizzes"
    assert reverse_roles["noun"]["anmqu"] == "facilities"
    assert reverse_roles["noun"]["kreng"] == "lens"

    public_precedence = {
        english_key: DEFAULT_GRAMMAR.pronouns[spec[0]]
        for english_key, spec in DEFAULT_GRAMMAR.english_pronouns.items()
    }
    assert set(default_preferences) == colliding_keys | set(public_precedence)
    for english_key, root in public_precedence.items():
        assert default_preferences[english_key] == root
    for english_key, root in default_preferences.items():
        assert root in roots_by_key[english_key]
        assert xenari.db.lookup(english_key)[0] == root
        assert xenari.lookup(english_key)[0] == root

    flattened_lookup_preferences = {
        (english_key, part_of_speech): root
        for part_of_speech, preferences in lookup_preferences.items()
        for english_key, root in preferences.items()
    }
    assert set(flattened_lookup_preferences) == same_pos_collisions
    for (english_key, part_of_speech), root in flattened_lookup_preferences.items():
        assert mappings[(english_key, root)] == part_of_speech
        assert xenari.lookup(english_key, part_of_speech=part_of_speech)[0] == root

    translation_only = {
        (
            review["english_key"],
            review["root"],
            review["translation_role_part_of_speech"],
        )
        for review in fixture["translation_only_reviews"]
    }
    assert translation_only == {
        ("heard", "xi", "particle"),
        ("reported", "xi", "particle"),
    }
    tagged_keys = {english_key for english_key, _root in mappings}
    mapped_roots = {root for _english_key, root in mappings}
    for english_key, root, part_of_speech in translation_only:
        assert translation_preferences[part_of_speech][english_key] == root
        assert mappings.get((english_key, root)) != part_of_speech
    for part_of_speech, preferences in translation_preferences.items():
        for english_key, root in preferences.items():
            assert root in mapped_roots
            assert english_key in tagged_keys or (
                english_key,
                root,
                part_of_speech,
            ) in translation_only

    assert len(reverse) == len(mapped_roots) == verification["mapped_roots"]
    assert verification["reversible_mapped_roots"] == verification["mapped_roots"]
    assert set(reverse) == mapped_roots
    assert len(set(reverse.values())) == len(reverse)
    for root, english_key in reverse.items():
        assert len(english_key) > 1
        assert english_key == " ".join(english_key.strip().lower().split())
        assert mappings[(english_key, root)] in PARTS_OF_SPEECH
        assert root in roots_by_key[english_key]
        if len(roots_by_key[english_key]) > 1:
            assert default_preferences[english_key] == root
        assert xenari.lookup(english_key)[0] == root
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
