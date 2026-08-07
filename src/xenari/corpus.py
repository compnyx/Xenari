"""Deterministic paragraph round-trip benchmark for real English samples."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Iterable, Mapping

from .paths import TRANSLATION_CORPUS
from .translate.report import build_translation_report

_DIAGNOSTIC_PREFIXES = (
    "[untranslated:",
    "[partial:",
    "[warning:",
    "[fragment:",
    "[unknown:",
)
_STATUS_RANK = {"unsupported": 0, "partial": 1, "complete": 2}


def load_translation_corpus() -> dict[str, Any]:
    """Load the packaged benchmark corpus."""
    return json.loads(TRANSLATION_CORPUS.read_text(encoding="utf-8"))


def _strip_diagnostics(text: str) -> str:
    """Remove balanced translator diagnostics so echoed source text cannot score."""
    output: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "[" and text.startswith(_DIAGNOSTIC_PREFIXES, index):
            depth = 0
            while index < len(text):
                if text[index] == "[":
                    depth += 1
                elif text[index] == "]":
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                index += 1
            continue
        output.append(text[index])
        index += 1
    cleaned = re.sub(r"\s+", " ", "".join(output))
    cleaned = re.sub(r"(?:^|\s)[.;]+(?=\s|$)", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" .;:")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", without_marks))


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_phrase = _normalize(phrase)
    return bool(normalized_phrase) and f" {normalized_phrase} " in f" {text} "


def score_units(round_trip: str, units: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Score manually declared meaning or grammar units against clean round-trip text."""
    normalized = _normalize(round_trip)
    retained: list[str] = []
    missing: list[str] = []
    for unit in units:
        groups = unit.get("terms", [])
        passed = bool(groups) and all(
            any(_contains_phrase(normalized, alternative) for alternative in alternatives)
            for alternatives in groups
        )
        (retained if passed else missing).append(str(unit["id"]))
    total = len(retained) + len(missing)
    score = round(100 * len(retained) / total, 1) if total else 100.0
    return {
        "score": score,
        "retained": len(retained),
        "total": total,
        "retained_units": retained,
        "missing_units": missing,
    }


def _case_baseline_failures(case: Mapping[str, Any], result: Mapping[str, Any]) -> list[str]:
    baseline = case["baseline"]
    failures: list[str] = []
    if _STATUS_RANK[result["status"]] < _STATUS_RANK[baseline["status"]]:
        failures.append(f"status fell below {baseline['status']}")
    if result["meaning"]["score"] < baseline["minimum_meaning_score"]:
        failures.append("meaning score regressed")
    if result["grammar"]["score"] < baseline["minimum_grammar_score"]:
        failures.append("grammar score regressed")
    if result["diagnostic_count"] > baseline["maximum_diagnostics"]:
        failures.append("diagnostic count increased")
    return failures


def run_translation_corpus(x, case_ids: Iterable[str] = ()) -> dict[str, Any]:
    """Translate, reverse, score, and compare the packaged real-text corpus."""
    corpus = load_translation_corpus()
    selected_ids = set(case_ids)
    known_ids = {case["id"] for case in corpus["cases"]}
    unknown = sorted(selected_ids - known_ids)
    if unknown:
        raise ValueError("unknown corpus case(s): " + ", ".join(unknown))

    cases = [case for case in corpus["cases"] if not selected_ids or case["id"] in selected_ids]
    results: list[dict[str, Any]] = []
    for case in cases:
        forward = x.speak(case["english"], evidential="assumed")
        forward_report = build_translation_report(
            source=case["english"], direction="english_to_xenari", output=forward
        )
        translatable_xenari = _strip_diagnostics(forward)
        reverse = x.reverse(translatable_xenari) if translatable_xenari else ""
        round_trip = _strip_diagnostics(reverse)
        meaning = score_units(round_trip, case["meaning_units"])
        grammar = score_units(round_trip, case["grammar_units"])
        result = {
            "id": case["id"],
            "source_type": case["source_type"],
            "tags": case["tags"],
            "source": case["english"],
            "forward": forward,
            "translatable_xenari": translatable_xenari,
            "round_trip": round_trip,
            "status": forward_report["status"],
            "diagnostic_count": len(forward_report["diagnostics"]),
            "meaning": meaning,
            "grammar": grammar,
        }
        result["baseline_failures"] = _case_baseline_failures(case, result)
        result["baseline_ok"] = not result["baseline_failures"]
        results.append(result)

    def totals(dimension: str) -> tuple[int, int]:
        return (
            sum(result[dimension]["retained"] for result in results),
            sum(result[dimension]["total"] for result in results),
        )

    meaning_retained, meaning_total = totals("meaning")
    grammar_retained, grammar_total = totals("grammar")
    retained = meaning_retained + grammar_retained
    total = meaning_total + grammar_total
    regressions = [result["id"] for result in results if not result["baseline_ok"]]
    strict_failures = [
        result["id"]
        for result in results
        if result["status"] != "complete"
        or result["meaning"]["score"] < 100
        or result["grammar"]["score"] < 100
    ]
    return {
        "schema": "xenari.translation-corpus-report.v1",
        "ok": not regressions,
        "strict_pass": not strict_failures,
        "case_count": len(results),
        "status_counts": {
            status: sum(result["status"] == status for result in results)
            for status in ("complete", "partial", "unsupported")
        },
        "diagnostic_count": sum(result["diagnostic_count"] for result in results),
        "meaning": {
            "score": round(100 * meaning_retained / meaning_total, 1) if meaning_total else 100.0,
            "retained": meaning_retained,
            "total": meaning_total,
        },
        "grammar": {
            "score": round(100 * grammar_retained / grammar_total, 1) if grammar_total else 100.0,
            "retained": grammar_retained,
            "total": grammar_total,
        },
        "overall_score": round(100 * retained / total, 1) if total else 100.0,
        "baseline_regressions": regressions,
        "strict_failures": strict_failures,
        "cases": results,
    }


def render_translation_corpus(report: Mapping[str, Any]) -> str:
    """Render the corpus report for humans without hiding individual failures."""
    lines = [
        "Xenari real-text corpus benchmark",
        f"Cases: {report['case_count']}",
        (
            "Status: "
            f"{report['status_counts']['complete']} complete, "
            f"{report['status_counts']['partial']} partial, "
            f"{report['status_counts']['unsupported']} unsupported"
        ),
        (
            f"Retention: {report['overall_score']:.1f}% overall | "
            f"meaning {report['meaning']['score']:.1f}% | "
            f"grammar {report['grammar']['score']:.1f}%"
        ),
        f"Diagnostics: {report['diagnostic_count']}",
        "",
    ]
    for case in report["cases"]:
        lines.append(
            f"{case['id']}: {case['status']}; meaning {case['meaning']['score']:.1f}%; "
            f"grammar {case['grammar']['score']:.1f}%; diagnostics {case['diagnostic_count']}"
        )
        if case["meaning"]["missing_units"]:
            lines.append("  missing meaning: " + ", ".join(case["meaning"]["missing_units"]))
        if case["grammar"]["missing_units"]:
            lines.append("  missing grammar: " + ", ".join(case["grammar"]["missing_units"]))
        if case["baseline_failures"]:
            lines.append("  BASELINE REGRESSION: " + "; ".join(case["baseline_failures"]))
    lines.extend(
        [
            "",
            "baseline: " + ("ok" if report["ok"] else "REGRESSION"),
            "strict corpus: " + ("pass" if report["strict_pass"] else "not yet passing"),
        ]
    )
    return "\n".join(lines)


__all__ = [
    "load_translation_corpus",
    "render_translation_corpus",
    "run_translation_corpus",
    "score_units",
]
