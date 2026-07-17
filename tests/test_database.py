"""Focused Xenari behavior tests."""

from .support import *

def test_base6_db_canon_and_legacy_aliases_are_marked():
    x = Xenari(REPO / "xenari.db")

    xang = x.db.lookup_root("xang")
    assert "base-6 place/group morpheme" in xang["meaning"]

    legacy_forms = {
        "zif": "ca xang ca",
        "pev": "ca xang vriq",
        "besmun": "ca xang prit",
        "vipezuz": "ca xang qang",
        "vnub": "ca xang cum",
        "cveqsrin": "vriq xang",
    }
    for root, productive in legacy_forms.items():
        row = x.db.lookup_root(root)
        assert row["category"] == "Legacy Numeral Aliases"
        assert productive in row["notes"]

    for english, root in {
        "plus": "plomt",
        "minus": "krut",
        "times": "vrot",
        "divided by": "flopq",
        "equals": "zlem",
        "greater than": "grak",
        "less than": "vlox",
        "ratio": "nok",
    }.items():
        assert x.lookup(english)[0] == root

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

    ok, review = x.review_report(limit=1)
    assert ok
    assert review.startswith("# Xenari QC Review Report")
    assert "Mode: read-only; no database writes" in review
    assert "## Curation Queue" in review
    assert "python3 xenari_tool.py curate --placeholder --limit 20" in review

def test_curation_sections_are_filterable_and_explain_hypotheses():
    x = Xenari(REPO / "xenari.db")

    placeholders = x.db.curation_report(
        limit=8,
        placeholder=True,
        phrases=False,
        relations=False,
    )
    assert "Placeholder category suggestions (grouped by suggestion)" in placeholders
    assert "  Action & Motion:" in placeholders
    assert "[high] (matched" in placeholders
    assert "Phrase-like definition review" not in placeholders
    assert "Relation candidate groups" not in placeholders

    candidates = x.db.relation_candidates()
    kinds = {candidate["kind"] for candidate in candidates}
    assert kinds == {
        "possible synonym",
        "possible register variant",
        "possible category clash",
        "possible false friend",
    }
    relations = x.db.curation_report(
        limit=1,
        placeholder=False,
        phrases=False,
        relations=True,
    )
    assert "hypotheses, not facts" in relations
    assert "possible synonym" in relations
    assert "preview only: python3 xenari_tool.py relate" in relations

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

def test_categorize_previews_guards_broad_writes_and_backs_up(tmp_path):
    db_path = tmp_path / "xenari.db"
    shutil.copy2(REPO / "xenari.db", db_path)
    x = Xenari(db_path)

    original = x.db.lookup_root("anhthu")["category"]
    ok, preview = x.db.categorize(root="anhthu")
    assert ok
    assert "Uncategorized -> Action & Motion" in preview
    assert "[high, eligible]" in preview
    assert "PREVIEW ONLY" in preview
    assert x.db.lookup_root("anhthu")["category"] == original

    ok, guarded = x.db.categorize(yes=True, limit=1)
    assert not ok
    assert "Refusing broad write" in guarded
    assert x.db.lookup_root("anhthu")["category"] == original

    ok, written = x.db.categorize(root="anhthu", yes=True)
    assert ok
    assert "Wrote 1 category change" in written
    assert x.db.lookup_root("anhthu")["category"] == "Action & Motion"
    assert list(tmp_path.glob("xenari.db.*.categorize.bak"))

    x.db.conn.execute(
        """INSERT INTO roots (root, meaning, category, source)
           VALUES ('xaz', 'friend carried by the wind', 'Uncategorized', 'test')"""
    )
    x.db.conn.commit()
    proposal = x.db.category_proposals(root="xaz")[0]
    assert proposal["confidence"] == "low"
    assert proposal["ambiguous"]

    ok, skipped = x.db.categorize(root="xaz", yes=True)
    assert ok
    assert "No eligible category changes" in skipped
    assert x.db.lookup_root("xaz")["category"] == "Uncategorized"

    ok, explicit = x.db.categorize(root="xaz", yes=True, include_ambiguous=True)
    assert ok
    assert "Wrote 1 category change" in explicit
    assert x.db.lookup_root("xaz")["category"] == proposal["suggested_category"]

def test_relate_is_preview_first_and_backs_up_explicit_writes(tmp_path):
    db_path = tmp_path / "xenari.db"
    shutil.copy2(REPO / "xenari.db", db_path)
    x = Xenari(db_path)
    roots = ("brak", "plonq")

    ok, preview = x.db.relate(*roots, relation="synonym")
    assert ok
    assert "curator assertion" in preview
    assert "PREVIEW ONLY" in preview
    assert not x.db.conn.execute(
        "SELECT 1 FROM semantic_relations WHERE root_a = ? AND root_b = ?",
        roots,
    ).fetchone()

    ok, written = x.db.relate(*roots, relation="synonym", yes=True)
    assert ok
    assert "Wrote 1 semantic relation" in written
    assert x.db.conn.execute(
        "SELECT 1 FROM semantic_relations WHERE root_a = ? AND root_b = ? AND relation = 'synonym'",
        roots,
    ).fetchone()
    assert list(tmp_path.glob("xenari.db.*.relate.bak"))

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

def test_read_only_db_open_does_not_initialize_or_write_and_write_open_still_creates(tmp_path):
    db_path = tmp_path / "readonly.db"
    shutil.copy2(REPO / "xenari.db", db_path)
    before = db_path.read_bytes()

    x = Xenari(db_path, read_only=True)
    assert x.db.lookup("man") == ("odsalsorq", "man")
    assert x.db.search("english", limit=1)
    x.db.close()
    assert db_path.read_bytes() == before
    assert not (tmp_path / "readonly.db-wal").exists()
    assert not (tmp_path / "readonly.db-shm").exists()

    created = tmp_path / "created.db"
    writable = XenariDB(created)
    assert writable.conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'roots'"
    ).fetchone()
    writable.close()
    assert not (tmp_path / "created.db-wal").exists()
    assert not (tmp_path / "created.db-shm").exists()

def test_invalid_root_is_blocked_without_database_mutation(tmp_path):
    db_path = tmp_path / "xenari.db"
    shutil.copy2(REPO / "xenari.db", db_path)
    db = XenariDB(db_path)
    before = db.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0]
    ok, messages = db.add_root("bad-root", "xqz", "invalid root", category="Tests")
    assert not ok
    assert any(message.startswith("BLOCKED: invalid root form:") for message in messages)
    assert db.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0] == before
    assert db.lookup("bad-root") is None

def test_search_ranks_all_matches_before_limiting_results():
    x = Xenari(REPO / "xenari.db", read_only=True)
    for term in ("man", "english"):
        expected_root, _ = x.db.lookup(term)
        results = x.db.search(term, limit=1)
        assert results[0]["root"] == expected_root

def test_repeated_lookup_misses_use_the_loaded_synonym_index():
    x = Xenari(REPO / "xenari.db", read_only=True)
    calls = 0
    original = x._meaning_keys

    def counted(meaning):
        nonlocal calls
        calls += 1
        return original(meaning)

    x._meaning_keys = counted
    for _ in range(20):
        assert x.lookup("definitely-not-a-xenari-meaning") == (None, None)
    assert calls == 0
