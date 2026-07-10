from pathlib import Path
import sys
import shutil
import json
import subprocess

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from xenari_tool import Xenari
from xenari_gap import GapHarvester


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


def test_multiclause_hardening_regression_is_bounded_and_honest():
    x = Xenari(REPO / "xenari.db")
    case = load_fixtures()["hardening"]

    translated = x.speak(case["regression_input"], evidential="assumed")

    assert translated == case["expected"]
    for fragment in case["must_include"]:
        assert fragment in translated
    for fragment in case["must_not_include"]:
        assert fragment not in translated
    assert translated.count("[partial:") == 1
    assert translated.startswith("prax. ")
    assert x.speak("hey friend", evidential="assumed") == "prax"


def test_smart_apostrophes_expand_like_ascii_apostrophes():
    x = Xenari(REPO / "xenari.db")

    ascii_forms = "I'm working; I've gotten the result; You've seen it; we'll go; I can't go"
    for apostrophe in ("’", "‘", "ʼ", "＇"):
        smart_forms = ascii_forms.replace("'", apostrophe)
        assert x._expand_english_contractions(smart_forms) == x._expand_english_contractions(ascii_forms)


def test_work_senses_and_unknown_subjects_do_not_become_fake_roots():
    x = Xenari(REPO / "xenari.db")

    assert x._merge_compounds(["red", "hat"]) == ["red", "hat"]
    assert "rlisbrid" not in x.speak("I love the red hat", evidential="assumed")
    assert x.speak("creative work", evidential="assumed") == "flonx"
    assert "flonx" not in x.speak("I work", evidential="assumed")
    assert x.speak("the elevator was not working", evidential="assumed") == (
        "ka nu spokta ta qxundraz nu lo xo ngu"
    )
    assert x.speak("the turbolift was not working", evidential="assumed").startswith(
        "[untranslated: the turbolift was not working;"
    )


def test_kiss_and_bite_use_distinct_canon_roots():
    x = Xenari(REPO / "xenari.db")

    assert x.lookup("kiss") == ("nquxe", "to kiss / to press lips together")
    assert x.lookup("bite") == ("qruq'", "to bite")
    assert x.speak("I kiss you", evidential="assumed") == "ra mex ka neq ta nquxe sa xo"
    assert x.speak("I bite you", evidential="assumed") == "ra mex ka neq ta qruq' sa xo"


def test_everyday_verb_overrides_use_established_roots():
    x = Xenari(REPO / "xenari.db")

    assert x._known_verb_root("hear") == "cromq"
    assert x._known_verb_root("heard") == "cromq"
    assert x._known_verb_root("listen") == "grip"
    assert x._known_verb_root("seen") == "toq"
    for form, root in {
        "build": "mrob",
        "built": "mrob",
        "say": "krimp",
        "said": "krimp",
        "touch": "qabrerd",
        "touched": "qabrerd",
        "slam": "tulo",
        "slammed": "tulo",
        "stop": "semax",
        "stopped": "semax",
        "break": "zont",
        "broke": "zont",
        "broken": "zont",
        "wait": "trekq",
        "run": "zaqa",
        "open": "xleq",
        "help": "pegzos",
        "find": "trek",
        "enter": "logi",
        "belong": "mifzxuri",
    }.items():
        assert x._known_verb_root(form) == root


def test_loop3_clause_corpus_is_bounded_shared_and_readable():
    x = Xenari(REPO / "xenari.db")
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 3]
    reverse = [case for case in fixtures["reverse"] if case.get("loop") == 3]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 10
    assert len(reverse) >= 4
    assert len(stress) >= 5
    assert {case["family"] for case in forward} >= {
        "conditional", "purpose", "relative", "temporal", "temporal-wh",
    }
    assert all("[untranslated:" not in case["xenari"] for case in forward)

    initial_when = x.speak("When does the door open?", evidential="assumed")
    temporal_when = x.speak("When the door opens, I run.", evidential="assumed")
    unsupported_relative = x.speak(
        "The alien that the woman said she saw ran.", evidential="assumed"
    )

    assert initial_when.startswith("[partial: unsupported WH question 'when':")
    assert temporal_when.startswith("su cruv ")
    assert unsupported_relative.startswith("qex [partial: unsupported relative clause:")
    assert all("kam" not in case["xenari"].split() for case in forward)


def test_loop4_modifier_corpus_is_bounded_shared_and_readable():
    x = Xenari(REPO / "xenari.db")
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 4]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 15
    assert len(stress) >= 6
    assert {case["family"] for case in forward} >= {
        "comparative", "conditional", "possessive", "purpose",
        "quantity", "relative", "superlative", "temporal",
    }
    assert all("[untranslated:" not in case["xenari"] for case in forward)

    comparative = x.speak("The alien is taller than the human.", evidential="assumed")
    superlative = x.speak("That is the fastest ship", evidential="assumed")
    no_water = x.speak("No water", evidential="assumed")
    no_people = x.speak("No people open the door.", evidential="assumed")

    assert comparative.startswith("ra sump maq ")
    assert "comparison-standard canon conflict" in comparative
    assert superlative == "ra nu suhpi kag qruv ka nu zra ta zux nu sa xo"
    assert no_water == "cruq nulxant"
    assert no_people == "ra nu zrump ka vi zifrelk nulxant ta xleq vi sa xo"
    assert "ngu" not in no_water.split()
    assert "ngu" not in no_people.split()
    for stale_root in {"qren", "trox", "xlu"}:
        assert stale_root not in comparative.split()


def test_loop5_dialogue_sound_and_imperative_corpus_is_bounded_and_honest():
    x = Xenari(REPO / "xenari.db")
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 5]
    reverse = [case for case in fixtures["reverse"] if case.get("loop") == 5]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 15
    assert len(reverse) >= 1
    assert len(stress) >= 7
    assert {case["family"] for case in forward} >= {
        "dialogue", "imperative", "quote", "sound", "sound-report",
        "stage-direction", "typography", "vocalization", "vocalization-gap",
    }
    assert x._known_verb_root("slams") == "tulo"
    assert x._known_verb_root("whispered") == "tyequga"

    repeated_beep = x.speak("Beep beep beep.", evidential="assumed")
    unknown_ugh = x.speak("Ugh...", evidential="assumed")
    negative_command = x.speak("Don't touch that!", evidential="assumed")

    assert repeated_beep == "nqozo nqozo nqozo"
    assert " nu" not in repeated_beep
    assert unknown_ugh == "[untranslated: ugh; no Xenari root for: ugh]"
    assert negative_command == "ra nu zra ta qabrerd vi ko xo ngu"
    assert " va" not in negative_command
    assert "ka neq" not in negative_command


def test_loop6_fuzz_safety_corpus_is_shared_and_honest():
    x = Xenari(REPO / "xenari.db")
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 6]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 10
    assert len(stress) >= 6
    assert {case["family"] for case in forward} >= {
        "empty-input", "imperative-gap", "speaker-label",
        "speaker-stage", "stage-direction",
    }

    assert x.speak("...", evidential="assumed") == "[untranslated: no translatable content]"
    assert x.speak("   ", evidential="assumed") == "[untranslated: no translatable content]"
    assert x.speak("Run!", evidential="assumed") == "[partial: unsupported imperative: run]"
    assert x.speak("Don't run.", evidential="assumed") == (
        "[partial: unsupported negated imperative: do not run]"
    )
    assert x.speak("NYX: Shhh.", evidential="assumed") == "shava"
    assert x.speak("MARA (O.S.): Beep beep.", evidential="assumed") == "nqozo nqozo"
    assert x.speak("(whispers) shhh.", evidential="assumed") == (
        "[partial: omitted subject for action: whisper]. shava"
    )
    assert "ka neq" not in x.speak("Run!", evidential="assumed")
    assert " va" not in x.speak("Don't run.", evidential="assumed")


def test_loop7_coordination_and_intransitive_fuzz_is_bounded():
    x = Xenari(REPO / "xenari.db")
    fixtures = load_fixtures()
    forward = [case for case in fixtures["forward"] if case.get("loop") == 7]
    stress = [case for case in forward if case.get("stress")]

    assert len(forward) >= 8
    assert len(stress) >= 5
    assert {case["family"] for case in forward} >= {
        "animacy", "coordination", "intransitive",
        "question", "question-gap", "speaker-stage",
    }

    assert x.speak("The door opens.", evidential="assumed") == "ka nu zrump ta xleq nu sa xo"
    assert x.speak("The alien runs quickly.", evidential="assumed") == (
        "ka vi qex ta zaqa vi sa xo"
    )
    assert x.speak("The dog runs slowly.", evidential="assumed") == (
        "ka vi zrenq ta zaqa vi sa xo"
    )
    assert x.speak("I run and she waits.", evidential="assumed") == (
        "ka neq ta zaqa sa xo. xen ka leq ta trekq sa xo"
    )
    assert x.speak("Why run?", evidential="assumed") == (
        "[partial: unsupported subjectless question: why run]"
    )
    assert "ra nu zrump ka neq ta xleq" not in x.speak("The door opens.", evidential="assumed")
    assert "ra nu xen" not in x.speak("I run and she waits.", evidential="assumed")


def test_loop3_reverse_reads_structured_clause_boundaries():
    x = Xenari(REPO / "xenari.db")

    assert x.reverse(
        "pevoq ra vi qex ka neq ta toq sa xo ti ka neq ta zaqa ve xo"
    ) == "if I see alien, then I will run"
    assert x.reverse(
        "su cruv ka nu zrump ta xleq nu sa xo ti ka neq ta zaqa sa xo"
    ) == "when door opens, I run"
    assert x.reverse(
        "ka vi habdazluc su zre ra nu zrump ta zont vi lo xo "
        "ti ta zaqa vi sa xo"
    ) == "person who broke door runs"


def test_content_questions_and_safe_noun_subjects_keep_their_roles():
    x = Xenari(REPO / "xenari.db")

    why = x.speak("Why did the elevator stop?", evidential="assumed")
    where = x.speak("Where will you go?", evidential="assumed")

    assert why == "voq ka nu spokta ta semax nu lo xo"
    assert where == "qur ka mex ta qeng ve xo"
    assert " va" not in why
    assert " va" not in where
    assert x.speak("Have you seen my hat?", evidential="assumed").endswith(" va")
    assert x.speak("Who broke the red window?", evidential="assumed") == (
        "[untranslated: who broke the red window; unsupported grammar: "
        "WH subject 'who' lacks a canon interrogative]"
    )
    assert x.speak("the elevator stopped", evidential="assumed") == (
        "ka nu spokta ta semax nu lo xo"
    )
    assert x.speak("the door slammed", evidential="assumed") == (
        "ka nu zrump ta tulo nu lo xo"
    )


def test_reverse_warns_when_recovering_malformed_clause_frames():
    x = Xenari(REPO / "xenari.db")
    malformed = (
        "to fa nu flonx ka nu hey ta qeng nu ve xo ngu na nu xenari "
        "ka nu qzecmru ta qranx nu sa xo mex"
    )

    reversed_text = x.reverse(malformed)

    assert "[unknown: hey] will not go" in reversed_text
    assert "anyway throw" in reversed_text
    assert "[warning:" in reversed_text
    assert "recovered separate fragments" in reversed_text


def test_auto_translate_and_inspect_helpers():
    x = Xenari(REPO / "xenari.db")

    assert x.translate("I love you", evidential="assumed") == "ra mex ka neq ta zrent sa xo"
    assert x.translate("ra mex ka neq ta zrent sa xa") == "I love you"
    assert x.translate("prax") == "hello"

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
        [sys.executable, "xenari_tool.py", "categorize", "--root", "anhthu", "--limit", "1"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert categorize.returncode == 0
    assert "Uncategorized -> Action & Motion" in categorize.stdout
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


def test_gap_harvest_captures_words_phrases_sounds_and_names(tmp_path):
    script = tmp_path / "script.txt"
    script.write_text(
        """INT. BLACK ROOM - NIGHT

NYX:
Hello Varek.

(FZZARR.)
LEE watches.
The rustglass elevator hums.
The rustglass elevator hums.
Her claws skittered across the floor.
""",
        encoding="utf-8",
    )
    x = Xenari(REPO / "xenari.db")
    harvester = GapHarvester(x)
    report = harvester.harvest_paths([script], phrase_min_count=2)
    buckets = report["buckets"]

    assert any(item["key"] == "fzzarr" for item in buckets["sound_effects"])
    assert any(item["key"] == "varek" for item in buckets["names_places"])
    assert any(item["key"] == "lee" for item in buckets["names_places"])
    assert any(item["key"] == "int" for item in buckets["script_format_markers"])
    assert any(item["key"] == "skittered" for item in buckets["lexical_gaps"])
    assert any(item["key"] == "the rustglass" for item in buckets["phrase_gaps"])
    assert not any(item["key"] == "int" for item in buckets["lexical_gaps"])
    assert not any(item["key"] == "lee" for item in buckets["lexical_gaps"])

    markdown = harvester.render_markdown(report, limit=5)
    assert "# Xenari Gap Harvest Report" in markdown
    assert "## Sound Effects" in markdown
    assert "## Phrase Gaps" in markdown
    assert "script.txt:" in markdown


def test_gap_harvest_normalizes_all_supported_apostrophes():
    x = Xenari(REPO / "xenari.db")
    harvester = GapHarvester(x)
    variants = ["I'm", "I’m", "I‘m", "Iʼm", "I＇m", "I`m"]

    reports = [
        harvester.harvest_documents([{"source": "dialogue", "text": variant}])
        for variant in variants
    ]

    bucket_keys = [
        {name: [item["key"] for item in entries] for name, entries in report["buckets"].items()}
        for report in reports
    ]
    assert all(keys == bucket_keys[0] for keys in bucket_keys[1:])
    assert bucket_keys[0]["covered_by_grammar"] == ["am"]


def test_gap_harvest_keeps_repeated_sounds_inline_speakers_and_stage_spans_separate():
    x = Xenari(REPO / "xenari.db")
    harvester = GapHarvester(x)
    report = harvester.harvest_documents([{
        "source": "dialogue",
        "text": "NYX: Ugh… KRRR KRRR.\nMARA:\n[FZZARR FZZARR] I run.\n",
    }], phrase_min_count=1, max_phrase_words=3)
    buckets = report["buckets"]

    ugh = next(item for item in buckets["vocalizations"] if item["key"] == "ugh")
    krrr = next(item for item in buckets["sound_effects"] if item["key"] == "krrr")
    fzzarr = next(item for item in buckets["sound_effects"] if item["key"] == "fzzarr")
    phrase_keys = {item["key"] for item in buckets["phrase_gaps"]}
    all_keys = {
        item["key"]
        for entries in buckets.values()
        for item in entries
    }

    assert ugh["count"] == 1
    assert ugh["contexts"][0]["speaker"] == "Nyx"
    assert krrr["count"] == 2
    assert krrr["contexts"][0]["speaker"] == "Nyx"
    assert fzzarr["count"] == 2
    assert fzzarr["contexts"][0]["speaker"] == "Mara"
    assert fzzarr["contexts"][0]["stage_direction"] is True
    assert "ugh krrr" not in phrase_keys
    assert "fzzarr i" not in phrase_keys
    assert "nyx" not in all_keys
    assert "mara" not in all_keys


def test_gaps_cli_writes_json_report(tmp_path):
    script = tmp_path / "script.txt"
    out = tmp_path / "gap-report.json"
    script.write_text("MARA:\nNnn. The rustglass door clicks.\nThe rustglass door clicks.\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "xenari_tool.py",
            "gaps",
            str(script),
            "--format",
            "json",
            "--output",
            str(out),
            "--phrase-min-count",
            "2",
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert f"wrote {out}" in result.stdout
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["documents"] == 1
    assert any(item["key"] == "nnn" for item in data["buckets"]["vocalizations"])
    assert any(item["key"] == "the rustglass" for item in data["buckets"]["phrase_gaps"])


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
