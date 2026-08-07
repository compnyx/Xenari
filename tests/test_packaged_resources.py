import json
import sqlite3
from importlib.resources import files

from xenari.paths import (
    COMMON_ENGLISH_POS_V2,
    COMMON_ENGLISH_POS_V3,
    COMMON_ENGLISH_POS_V4,
    CORE_VOCABULARY_POS,
    OGDEN_BASIC_ENGLISH,
    POST_V4_LEXICON,
    RUNTIME_CONTRACT,
    TRANSLATION_CORPUS,
    TRANSLATOR_FIXTURES,
    generated_dictionary_path,
    generated_runtime_path,
    resolve_repo_root,
)
from xenari.runtime import RUNTIME_SCHEMA_VERSION


def test_translator_fixtures_are_available_as_package_data():
    resource = files("xenari").joinpath("data", "translator-fixtures.json")

    assert resource.is_file()
    assert TRANSLATOR_FIXTURES == resource

    fixtures = json.loads(resource.read_text(encoding="utf-8"))
    assert fixtures["forward"]
    assert fixtures["reverse"]


def test_translation_corpus_is_available_as_package_data():
    resource = files("xenari").joinpath("data", "translation-corpus.json")

    assert resource.is_file()
    assert TRANSLATION_CORPUS == resource
    corpus = json.loads(resource.read_text(encoding="utf-8"))
    assert corpus["schema"] == "xenari.translation-corpus.v1"
    assert len(corpus["cases"]) == 5


def test_runtime_contract_is_available_as_package_data():
    assert RUNTIME_CONTRACT.is_file()
    contract = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "xenari-runtime"
    assert contract["schema_version"] == RUNTIME_SCHEMA_VERSION


def test_post_v4_lexicon_preferences_are_available_as_package_data():
    assert POST_V4_LEXICON.is_file()
    fixture = json.loads(POST_V4_LEXICON.read_text(encoding="utf-8"))
    assert fixture["schema"] == "xenari.post-v4-lexicon.v1"
    assert len(fixture["mappings"]) == 11


def test_ogden_baseline_is_available_as_package_data():
    assert OGDEN_BASIC_ENGLISH.is_file()
    baseline = json.loads(OGDEN_BASIC_ENGLISH.read_text(encoding="utf-8"))
    assert baseline["schema"] == "xenari.ogden-basic-english.v1"
    assert baseline["source"]["accepted_form_count"] == 852


def test_core_vocabulary_pos_fixture_is_available_as_package_data():
    assert CORE_VOCABULARY_POS.is_file()
    fixture = json.loads(CORE_VOCABULARY_POS.read_text(encoding="utf-8"))
    assert fixture["schema"] == "xenari.core-vocabulary-pos.v1"
    assert sum(len(rows) for rows in fixture["mappings"].values()) == 175


def test_common_english_pos_v2_fixture_is_available_as_package_data():
    assert COMMON_ENGLISH_POS_V2.is_file()
    fixture = json.loads(COMMON_ENGLISH_POS_V2.read_text(encoding="utf-8"))
    assert fixture["schema"] == "xenari.common-english-pos.v2"
    assert fixture["scope"]["mapping_count"] == 199
    assert fixture["scope"]["tagged_mapping_count"] == 153
    assert fixture["scope"]["newly_tagged_count"] == 140
    assert fixture["scope"]["deferred_mapping_count"] == 46


def test_common_english_pos_v3_fixture_is_available_as_package_data():
    assert COMMON_ENGLISH_POS_V3.is_file()
    fixture = json.loads(COMMON_ENGLISH_POS_V3.read_text(encoding="utf-8"))
    assert fixture["schema"] == "xenari.common-english-pos.v3"
    assert fixture["scope"]["mapping_count"] == 1028
    assert fixture["scope"]["newly_tagged_count"] == 1000
    assert fixture["scope"]["deferred_mapping_count"] == 28


def test_common_english_pos_v4_fixture_is_available_as_package_data():
    assert COMMON_ENGLISH_POS_V4.is_file()
    fixture = json.loads(COMMON_ENGLISH_POS_V4.read_text(encoding="utf-8"))
    assert fixture["schema"] == "xenari.common-english-pos.v4"
    assert fixture["scope"]["source_mapping_count"] == 9325
    assert fixture["verification"]["unknown_part_of_speech"] == 0
    assert fixture["verification"]["reversible_mapped_roots"] == fixture[
        "verification"
    ]["mapped_roots"]


def test_packaged_canon_contains_migrated_part_of_speech_metadata():
    resource = files("xenari").joinpath("data", "xenari.db")

    with sqlite3.connect(resource) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(english_map)")}
        assert "part_of_speech" in columns
        annotated = conn.execute(
            "SELECT COUNT(*) FROM english_map WHERE part_of_speech IS NOT NULL"
        ).fetchone()[0]
        unknown = conn.execute(
            "SELECT COUNT(*) FROM english_map WHERE part_of_speech IS NULL"
        ).fetchone()[0]
        assert annotated > 0
        assert unknown == 0


def test_repository_outputs_are_resolved_explicitly():
    repo_root = resolve_repo_root()

    assert repo_root is not None
    assert generated_dictionary_path() == repo_root / "data" / "xenari-dict.json"
    assert generated_runtime_path() == (
        repo_root / "src" / "xenari" / "data" / "xenari-runtime.json"
    )


def test_repository_output_honors_runtime_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv("XENARI_REPO_ROOT", str(tmp_path))

    assert generated_dictionary_path() == tmp_path / "data" / "xenari-dict.json"
    assert generated_runtime_path() == (
        tmp_path / "src" / "xenari" / "data" / "xenari-runtime.json"
    )
