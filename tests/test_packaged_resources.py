import json
from importlib.resources import files

from xenari.paths import TRANSLATOR_FIXTURES, generated_dictionary_path, resolve_repo_root


def test_translator_fixtures_are_available_as_package_data():
    resource = files("xenari").joinpath("data", "translator-fixtures.json")

    assert resource.is_file()
    assert TRANSLATOR_FIXTURES == resource

    fixtures = json.loads(resource.read_text(encoding="utf-8"))
    assert fixtures["forward"]
    assert fixtures["reverse"]


def test_repository_outputs_are_resolved_explicitly():
    repo_root = resolve_repo_root()

    assert repo_root is not None
    assert generated_dictionary_path() == repo_root / "data" / "xenari-dict.json"
