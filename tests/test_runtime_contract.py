import json
import subprocess
import sys

import pytest

from xenari.grammar import DEFAULT_GRAMMAR
from xenari.runtime import (
    RUNTIME_SCHEMA,
    RUNTIME_SCHEMA_VERSION,
    build_runtime_contract,
    check_runtime_export,
    runtime_json,
    sync_runtime_exports,
)
from xenari.runtime_tables import (
    BASE6_DIGIT_ROOTS,
    BASE6_NUMBER_WORDS,
    BASE6_PLACE_ROOT,
    ENGLISH_CONTRACTIONS,
    FORWARD_PREFERRED,
    LOOKUP_PREFERRED_BY_PART_OF_SPEECH,
    MATH_OPERATOR_ROOTS,
    REVERSE_PLURAL_NOUN_ROOTS,
    REVERSE_PREFERRED,
    REVERSE_PREFERRED_BY_PART_OF_SPEECH,
    REVERSE_PRONOUNS,
    REVERSE_VERB_INFLECTIONS,
    SENTENCE_FINAL_TEMPORALS,
    TEMPORAL_GLOSSES,
    TRANSLATION_PREFERRED_BY_PART_OF_SPEECH,
)

from .support import REPO


def test_runtime_contract_is_deterministic_and_json_safe():
    first = runtime_json()
    second = runtime_json()
    contract = json.loads(first)

    assert first == second
    assert first.endswith("\n")
    assert contract["schema"] == RUNTIME_SCHEMA
    assert contract["schema_version"] == RUNTIME_SCHEMA_VERSION
    assert contract["grammar"] == DEFAULT_GRAMMAR.to_runtime_dict()
    assert contract == build_runtime_contract()


def test_runtime_contract_contains_the_python_translation_tables():
    contract = build_runtime_contract()

    assert contract["numbers"]["base6_digit_roots"] == {
        str(key): value for key, value in BASE6_DIGIT_ROOTS.items()
    }
    assert contract["numbers"]["base6_number_words"] == dict(BASE6_NUMBER_WORDS)
    assert contract["numbers"]["base6_place_root"] == BASE6_PLACE_ROOT
    assert contract["numbers"]["math_operator_roots"] == dict(MATH_OPERATOR_ROOTS)
    assert contract["normalization"]["contractions"] == dict(ENGLISH_CONTRACTIONS)
    assert contract["normalization"]["sentence_final_temporals"] == dict(
        SENTENCE_FINAL_TEMPORALS
    )
    assert contract["forward"]["preferred"] == dict(FORWARD_PREFERRED)
    assert contract["forward"]["lookup_preferred_by_part_of_speech"] == {
        part_of_speech: dict(preferences)
        for part_of_speech, preferences in LOOKUP_PREFERRED_BY_PART_OF_SPEECH.items()
    }
    assert contract["forward"]["translation_preferred_by_part_of_speech"] == {
        part_of_speech: dict(preferences)
        for part_of_speech, preferences in TRANSLATION_PREFERRED_BY_PART_OF_SPEECH.items()
    }
    assert contract["forward"]["translation_preferred_by_part_of_speech"]["verb"]["sent"] == "bern"
    assert contract["reverse"]["pronouns"] == {
        root: dict(forms) for root, forms in REVERSE_PRONOUNS.items()
    }
    assert contract["reverse"]["preferred"] == dict(REVERSE_PREFERRED)
    assert contract["reverse"]["preferred_by_part_of_speech"] == {
        part_of_speech: dict(preferences)
        for part_of_speech, preferences in (
            REVERSE_PREFERRED_BY_PART_OF_SPEECH.items()
        )
    }
    assert contract["reverse"]["plural_noun_roots"] == sorted(
        REVERSE_PLURAL_NOUN_ROOTS
    )
    assert contract["reverse"]["verb_inflections"] == {
        root: dict(forms) for root, forms in REVERSE_VERB_INFLECTIONS.items()
    }
    assert len(contract["reverse"]["verb_inflections"]) == 2389
    assert contract["reverse"]["verb_inflections"]["gluzto"] == {
        "past": "played",
        "third_person": "plays",
    }
    assert contract["reverse"]["verb_inflections"]["tyequga"] == {
        "past": "rustled",
        "third_person": "rustles",
    }
    assert contract["reverse"]["preferred_by_part_of_speech"]["verb"]["tyequga"] == (
        "rustle"
    )
    assert contract["reverse"]["preferred_by_part_of_speech"]["noun"]["anmqu"] == (
        "facilities"
    )
    assert contract["reverse"]["preferred"]["vehya"] == "potato"
    reviewed_reverse_preferences = {
        "calar": "decreasing",
        "hevu": "jammed",
        "kloxi": "inflated",
        "sfupzhaq": "momentarily",
        "shicey": "increasing",
        "sisolse": "mimicking",
        "trala": "intended",
        "verun": "authored",
        "xoqom": "whirling",
        "zeyor": "hovers",
        "zoqevel": "constructed",
        "zukaqop": "disconnects",
    }
    assert {
        root: contract["reverse"]["preferred"][root]
        for root in reviewed_reverse_preferences
    } == reviewed_reverse_preferences
    assert contract["reverse"]["temporal_glosses"] == dict(TEMPORAL_GLOSSES)
    assert set(contract["part_of_speech"]["browser_codes"]) == set(
        contract["part_of_speech"]["controlled_vocabulary"]
    )


def test_translation_mixins_use_shared_tables(xenari):
    assert xenari._base6_digit_roots() is BASE6_DIGIT_ROOTS
    assert xenari._base6_number_words() is BASE6_NUMBER_WORDS
    assert xenari._math_operator_roots() is MATH_OPERATOR_ROOTS
    assert xenari._sentence_final_temporals is SENTENCE_FINAL_TEMPORALS
    assert xenari._expand_english_contractions("I'm gonna go") == "i am going to go"


def test_runtime_sync_writes_one_package_artifact_and_optional_site_copies(
    monkeypatch,
    tmp_path,
):
    repo = tmp_path / "repo"
    site = tmp_path / "site"
    monkeypatch.setenv("XENARI_REPO_ROOT", str(repo))

    paths = sync_runtime_exports(include_site=True, site_root=site)

    expected = [
        repo / "src" / "xenari" / "data" / "xenari-runtime.json",
        site / "src" / "data" / "xenari-runtime.json",
        site / "public" / "xenari-runtime-data.json",
    ]
    assert paths == expected
    assert all(path.read_text(encoding="utf-8") == runtime_json() for path in expected)
    assert check_runtime_export(expected[0]).endswith("xenari-runtime.json")


def test_runtime_check_rejects_stale_artifact(tmp_path):
    stale = tmp_path / "runtime.json"
    payload = build_runtime_contract()
    payload["schema_version"] = -1
    stale.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="out of date"):
        check_runtime_export(stale)


def test_export_runtime_cli_prints_and_checks_the_contract():
    printed = subprocess.run(
        [sys.executable, "xenari_tool.py", "export-runtime"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert printed.returncode == 0, printed.stderr
    assert json.loads(printed.stdout) == build_runtime_contract()

    checked = subprocess.run(
        [sys.executable, "xenari_tool.py", "export-runtime", "--check"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "export-runtime: ok" in checked.stdout
