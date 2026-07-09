from pathlib import Path
import sys
import shutil

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from xenari_tool import Xenari


def test_known_phrase_generation():
    x = Xenari(REPO / "xenari.db")

    cases = {
        "I love you": "ra mex ka neq ta zrent sa xo",
        "you little bitch": "mex krengk frem",
        "I see the alien": "ra vi qex ka neq ta toq sa xo",
        "the alien sees me": "ra neq ka vi qex ta toq vi sa xo",
        "the alien is dangerous": "ra fatyih ka vi qex ta zux vi sa xo",
        "the hat is red": "ra rlis ka nu brid ta zux nu sa xo",
        "I approach the figure by the lake. The figure's hat blows off": (
            "ra vi loco na nu qlon ka neq ta frig sa xo. "
            "ra vi loco po brid ka vi cuq ta qruq vi sa xo"
        ),
    }

    for english, expected in cases.items():
        assert x.speak(english, evidential="assumed") == expected


def test_lookup_prefers_pronouns_and_synonyms():
    x = Xenari(REPO / "xenari.db")

    assert x.lookup("you")[0] == "mex"
    assert x.lookup("me")[0] == "neq"
    assert x.lookup("wrath")[0] == "nud"
    assert x.lookup("perilous")[0] == "fatyih"


def test_audit_has_no_actionable_qc_failures():
    x = Xenari(REPO / "xenari.db")
    audit = x.db.audit(limit=5)

    assert "Actionable exact duplicate groups: 0" in audit
    assert "Stale/conflict/reanalysis marker rows: 0" in audit
    assert "Phonotactic validator failures: 0" in audit


def test_info_and_validation_helpers():
    x = Xenari(REPO / "xenari.db")

    assert "dangerous" in x.info("fatyih")
    assert x.info("fatwih") == "unknown root"

    ok, report = x.validate_roots(["fatyih", "qip", "xqz"])
    assert not ok
    assert "fatyih: ok" in report
    assert "q followed by i" in report
    assert "root must contain at least one vowel" in report


def test_doctor_health_check():
    x = Xenari(REPO / "xenari.db")

    ok, report = x.doctor()
    assert ok
    assert "audit: ok" in report
    assert "lookup: ok" in report
    assert "speak: ok" in report


def test_mutation_previews_do_not_write(tmp_path):
    db_path = tmp_path / "xenari.db"
    shutil.copy2(REPO / "xenari.db", db_path)
    x = Xenari(db_path)

    ok, messages = x.db.add_root(
        "testroot",
        "xaz",
        "temporary test root",
        category="Tests",
        dry_run=True,
    )
    assert ok
    assert any("DRY RUN" in message for message in messages)
    assert x.db.lookup("testroot") is None

    ok, report = x.db.describe_remove_root("fatyih")
    assert ok
    assert "Remove preview for fatyih" in report
    assert "English mappings:" in report

    ok, report = x.db.describe_english_mapping("danger-test", "fatyih", context_note="test")
    assert ok
    assert "Map preview: danger-test -> fatyih" in report
    assert x.db.lookup("danger-test") is None


def test_remove_cleans_dependent_rows(tmp_path):
    db_path = tmp_path / "xenari.db"
    shutil.copy2(REPO / "xenari.db", db_path)
    x = Xenari(db_path)

    assert x.db.add_root("tempone", "xaz", "temporary one", category="Tests")[0]
    assert x.db.add_root("temptwo", "xoz", "temporary two", category="Tests")[0]
    x.db.conn.execute(
        "INSERT INTO compounds (compound_root, component_root, position) VALUES (?, ?, ?)",
        ("xaz", "xoz", 1),
    )
    x.db.conn.execute(
        "INSERT INTO semantic_relations (root_a, root_b, relation, notes) VALUES (?, ?, ?, ?)",
        ("xaz", "xoz", "test", "temporary"),
    )
    x.db.conn.commit()

    assert x.db.remove_root("xoz")
    assert x.db.lookup("temptwo") is None
    assert x.db.conn.execute(
        "SELECT COUNT(*) FROM compounds WHERE compound_root = ? OR component_root = ?",
        ("xoz", "xoz"),
    ).fetchone()[0] == 0
    assert x.db.conn.execute(
        "SELECT COUNT(*) FROM semantic_relations WHERE root_a = ? OR root_b = ?",
        ("xoz", "xoz"),
    ).fetchone()[0] == 0
