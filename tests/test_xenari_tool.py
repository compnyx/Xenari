from pathlib import Path
import sys
import shutil
import json

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from xenari_tool import Xenari


def load_fixtures():
    return json.loads((REPO / "data" / "translator-fixtures.json").read_text(encoding="utf-8"))


def test_known_phrase_generation():
    x = Xenari(REPO / "xenari.db")
    fixtures = load_fixtures()

    for case in fixtures["forward"]:
        assert x.speak(case["english"], evidential="assumed") == case["xenari"]


def test_reverse_uses_shared_fixtures():
    x = Xenari(REPO / "xenari.db")
    fixtures = load_fixtures()

    for case in fixtures["reverse"]:
        assert x.reverse(case["xenari"]) == case["english"]


def test_auto_translate_and_inspect_helpers():
    x = Xenari(REPO / "xenari.db")

    assert x.translate("I love you", evidential="assumed") == "ra mex ka neq ta zrent sa xo"
    assert x.translate("ra mex ka neq ta zrent sa xa") == "I love you"

    report = x.inspect_term("fatyih")
    assert "Root: fatyih" in report
    assert "dangerous" in report
    assert "Review-near meanings:" in report


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


def test_ranked_search_proposals_relations_lint_and_meta():
    x = Xenari(REPO / "xenari.db")

    search = x.db.search("dangerous", limit=5)
    assert search
    assert search[0]["root"] == "fatyih"
    assert search[0]["score"] > 0

    proposals = x.db.propose_root("glimmer", "soft unsteady light", limit=3)
    assert len(proposals) == 3
    assert all(not x.db.has_root(item["root"]) for item in proposals)
    assert all(not x.db.validate_phonotactics(item["root"]) for item in proposals)
    assert proposals[0]["score"] >= proposals[-1]["score"]
    assert proposals[0]["category"] == "Elements & Nature"
    assert not any("kgl" in item["root"] for item in proposals[:2])
    assert x.db._guess_category("wrath", "hot sharp anger") == "Mental & Abstract"

    ok, report = x.db.relations_report("fatyih")
    assert ok
    assert "fatyih" in report
    assert "Relations:" in report

    assert "Xenari lint" in x.db.lint(limit=3)
    curation = x.db.curation_report(limit=3)
    assert "Xenari curation report" in curation
    assert "Placeholder category suggestions" in curation
    assert "Relation candidate groups" in curation
    assert "schema_version" in x.db.metadata_report()

    ok, workbench = x.workbench(limit=2)
    assert ok
    assert "Xenari workbench" in workbench
    assert "Useful next commands:" in workbench
    assert "translator parity: ok" in workbench


def test_parity_and_coin_workflow_preview():
    x = Xenari(REPO / "xenari.db")

    ok, parity = x.parity()
    assert ok
    assert "forward: ok" in parity
    assert "reverse: ok" in parity

    ok, scout = x.coin_root("glimmer", "soft unsteady light", limit=3)
    assert ok
    assert "Coin root:" in scout
    assert "Candidate roots:" in scout
    assert "No write requested." in scout

    root = x.db.propose_root("glimmer", "soft unsteady light", limit=1)[0]["root"]
    ok, preview = x.coin_root("glimmer", "soft unsteady light", root=root, limit=3, dry_run=True)
    assert ok
    assert "DRY RUN" in preview
    assert x.db.lookup("glimmer") is None


def test_unified_export_and_reverse_helpers(tmp_path):
    x = Xenari(REPO / "xenari.db")

    assert x.export_format("json").lstrip().startswith("[")
    assert "const DICT" in x.export_format("js")

    out = tmp_path / "lexicon.md"
    assert "wrote" in x.export_format("md", output=out)
    assert out.exists()


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
