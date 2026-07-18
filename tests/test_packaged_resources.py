import json
import sqlite3
from importlib.resources import files

from xenari.paths import (
    RUNTIME_CONTRACT,
    TRANSLATOR_FIXTURES,
    generated_dictionary_path,
    generated_runtime_path,
    resolve_repo_root,
)


def test_translator_fixtures_are_available_as_package_data():
    resource = files("xenari").joinpath("data", "translator-fixtures.json")

    assert resource.is_file()
    assert TRANSLATOR_FIXTURES == resource

    fixtures = json.loads(resource.read_text(encoding="utf-8"))
    assert fixtures["forward"]
    assert fixtures["reverse"]


def test_runtime_contract_is_available_as_package_data():
    assert RUNTIME_CONTRACT.is_file()
    contract = json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "xenari-runtime"
    assert contract["schema_version"] == 1


def test_packaged_canon_contains_migrated_part_of_speech_metadata():
    resource = files("xenari").joinpath("data", "xenari.db")

    with sqlite3.connect(resource) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(english_map)")}
        assert "part_of_speech" in columns
        annotated = conn.execute(
            "SELECT COUNT(*) FROM english_map WHERE part_of_speech IS NOT NULL"
        ).fetchone()[0]
        assert annotated > 0


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
