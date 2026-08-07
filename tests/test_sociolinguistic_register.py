"""Structured sociolinguistic-register contract tests."""

import json

REGISTER_ROOTS = {
    "qrazhel",
    "qronkqrep",
    "qubihqrap",
    "plenkfrek",
    "xlekqfrek",
    "zlekkroxzal",
    "tuputlor",
}


def test_canon_exports_reviewed_register_metadata(xenari):
    exported = {row["root"]: row for row in json.loads(xenari.export_json())}

    assert {
        root for root, row in exported.items() if "sociolinguistic_register" in row
    } == REGISTER_ROOTS
    aeral = exported["qronkqrep"]["sociolinguistic_register"]
    assert aeral["register_class"] == "ethnic_slur"
    assert aeral["target_group"] == "Aeral people"
    assert aeral["literal_gloss"] == "bird-brain"
    assert aeral["severity"] == 2
    assert aeral["taboo_level"] == "offensive"
    assert "wind-song" in aeral["historical_basis"]
    assert "dumb Polack" in aeral["pragmatic_force"]
    assert "not a neutral synonym" in aeral["usage_note"]
    human = exported["tuputlor"]["sociolinguistic_register"]
    assert human["severity"] == 5
    assert human["taboo_level"] == "extreme"
    assert "Flesh Levy" in human["historical_basis"]
    assert "N-word" in human["pragmatic_force"]


def test_register_batch_is_guarded_and_atomic(writable_xenari):
    existing = writable_xenari.db.register_metadata("qronkqrep")
    assert existing is not None
    update = {**existing, "severity": 3}

    ok, preview = writable_xenari.db.set_register_metadata_batch([update])
    assert ok
    assert "PREVIEW ONLY" in preview
    assert writable_xenari.db.register_metadata("qronkqrep")["severity"] == 2

    ok, error = writable_xenari.db.set_register_metadata_batch(
        [{**update, "severity": 6}], yes=True
    )
    assert not ok
    assert "integer from 1 to 5" in error
    assert writable_xenari.db.register_metadata("qronkqrep")["severity"] == 2

    ok, report = writable_xenari.db.set_register_metadata_batch([update], yes=True)
    assert ok
    assert "Wrote 1" in report
    assert writable_xenari.db.register_metadata("qronkqrep")["severity"] == 3


def test_python_gloss_and_inspection_expose_register_force(xenari):
    gloss = xenari.gloss("The Aeral is a birdbrain", evidential="assumed")
    assert "ethnic slur targeting Aeral people" in gloss
    assert "severity 2/5, offensive" in gloss
    assert "literal bird-brain" in gloss

    inspected = xenari.inspect_term("tuputlor")
    assert "racial slur, severity 5/5, extreme" in inspected
    assert "History:" in inspected and "Flesh Levy" in inspected
    assert "Pragmatic force:" in inspected and "N-word" in inspected
