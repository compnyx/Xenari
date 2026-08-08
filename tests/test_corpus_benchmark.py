"""Real-text round-trip benchmark regressions."""

import pytest

from xenari.corpus import load_translation_corpus, run_translation_corpus, score_units


def test_real_text_corpus_is_structured_unique_and_intentionally_difficult():
    corpus = load_translation_corpus()
    cases = corpus["cases"]
    ids = [case["id"] for case in cases]

    assert corpus["schema"] == "xenari.translation-corpus.v1"
    assert len(cases) == 5
    assert len(ids) == len(set(ids))
    assert all(case["meaning_units"] for case in cases)
    assert all(case["grammar_units"] for case in cases)
    assert {tag for case in cases for tag in case["tags"]} >= {
        "proper-nouns", "date-range", "passive", "ellipsis", "relative-clause"
    }


def test_unit_scorer_requires_every_group_but_allows_explicit_alternatives():
    units = [
        {"id": "agent", "terms": [["unauthorized"], ["organisation", "organization"]]},
        {"id": "date", "terms": [["3rd of february", "third of february"]]},
        {"id": "missing", "terms": [["sengoku"], ["period"]]},
    ]
    report = score_units(
        "An unauthorized organization attends on the third of February.", units
    )

    assert report["score"] == 66.7
    assert report["retained_units"] == ["agent", "date"]
    assert report["missing_units"] == ["missing"]


def test_corpus_scores_only_clean_round_trip_content_and_locks_progress(xenari):
    report = run_translation_corpus(xenari)

    assert report["schema"] == "xenari.translation-corpus-report.v1"
    assert report["case_count"] == 5
    assert report["status_counts"] == {"complete": 3, "partial": 0, "unsupported": 2}
    assert report["meaning"]["retained"] == 24
    assert report["grammar"]["retained"] == 11
    assert report["overall_score"] == 67.3
    assert report["ok"] is True
    assert report["strict_pass"] is False
    assert report["baseline_regressions"] == []
    assert all(case["baseline_ok"] for case in report["cases"])
    data_breach = next(
        case for case in report["cases"] if case["id"] == "simplewiki-data-breach"
    )
    assert data_breach["status"] == "complete"
    assert data_breach["meaning"]["score"] == 100
    assert data_breach["grammar"]["score"] == 100
    assert data_breach["diagnostic_count"] == 0
    titans = next(
        case for case in report["cases"] if case["id"] == "simplewiki-titans-horizon"
    )
    assert titans["meaning"]["score"] == 100
    assert titans["grammar"]["score"] == 100
    assert titans["diagnostic_count"] == 0
    colloquial = next(
        case for case in report["cases"] if case["id"] == "colloquial-football-date"
    )
    assert colloquial["meaning"]["score"] == 100
    assert colloquial["diagnostic_count"] == 0


def test_corpus_case_filter_is_exact_and_rejects_typos(xenari):
    report = run_translation_corpus(xenari, ["simplewiki-titans-horizon"])
    assert [case["id"] for case in report["cases"]] == ["simplewiki-titans-horizon"]

    with pytest.raises(ValueError, match=r"^unknown corpus case\(s\): not-a-real-case$"):
        run_translation_corpus(xenari, ["not-a-real-case"])
