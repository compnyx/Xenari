"""Source-pinned common-English coverage checks."""

import json

from xenari.paths import OGDEN_BASIC_ENGLISH


def test_ogden_source_slots_and_approved_mappings_are_verified(xenari):
    baseline = json.loads(OGDEN_BASIC_ENGLISH.read_text(encoding="utf-8"))
    groups = {group["id"]: group for group in baseline["groups"]}
    report = xenari.ogden_baseline_report()

    assert {name: len(group["entries"]) for name, group in groups.items()} == {
        "operations": 100,
        "things-general": 400,
        "things-picturable": 200,
        "qualities-general": 100,
        "qualities-opposites": 50,
    }
    assert report["source"] == {
        "slot_count": 850,
        "accepted_form_count": 852,
        "normalized_slot_sha256": "8f9be7cf6fbbcb82b24ed5cdf38e9fa548ad74cb3b7e1119256cbc759aeaad03",
    }
    assert report["coverage"]["statuses"] == {
        "approved": 53,
        "pending": 797,
        "unsupported": 0,
    }
    assert report["coverage"]["direct_mapping_forms"] >= 10
    assert report["coverage"]["pos_matched_forms"] >= 10
    assert report["approved_failures"] == []
    assert report["errors"] == []
    assert report["ok"]


def test_ogden_strict_mode_exposes_the_remaining_review_queue(xenari):
    report = xenari.ogden_baseline_report(strict=True)

    assert not report["ok"]
    assert report["errors"] == []
    assert len(report["strict_blockers"]) == 797
    assert "operations-006" in report["strict_blockers"]
