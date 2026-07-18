"""Generate and synchronize the versioned cross-runtime Xenari contract."""

import json
import os
from importlib.resources import files
from pathlib import Path
from typing import Optional, Union

from ._version import __version__
from .db.pos import PARTS_OF_SPEECH
from .grammar import DEFAULT_GRAMMAR, GrammarConfig
from .paths import generated_runtime_path, resolve_repo_root, resolve_site_root
from .runtime_tables import (
    BASE6_DIGIT_ROOTS,
    BASE6_NUMBER_WORDS,
    BASE6_PLACE_ROOT,
    ENGLISH_CONTRACTIONS,
    ENGLISH_MATH_OPERATORS,
    MATH_OPERATOR_ROOTS,
    REVERSE_PREFERRED,
    REVERSE_PRONOUNS,
    SENTENCE_FINAL_TEMPORALS,
    TEMPORAL_GLOSSES,
)

RUNTIME_SCHEMA = "xenari-runtime"
RUNTIME_SCHEMA_VERSION = 1
PACKAGED_RUNTIME = files("xenari").joinpath("data").joinpath("xenari-runtime.json")

PART_OF_SPEECH_BROWSER_CODES = {
    "adjective": "adj",
    "adverb": "adv",
    "ideophone": "ideo",
    "interjection": "intj",
    "noun": "n",
    "numeral": "num",
    "particle": "part",
    "pronoun": "pron",
    "proper_noun": "propn",
    "verb": "v",
}


def build_runtime_contract(grammar: GrammarConfig = DEFAULT_GRAMMAR) -> dict[str, object]:
    """Return the deterministic JSON-safe contract used outside Python."""
    if set(PART_OF_SPEECH_BROWSER_CODES) != set(PARTS_OF_SPEECH):
        raise RuntimeError("runtime POS codes do not match the controlled vocabulary")
    return {
        "schema": RUNTIME_SCHEMA,
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "xenari_version": __version__,
        "grammar": grammar.to_runtime_dict(),
        "numbers": {
            "base6_place_root": BASE6_PLACE_ROOT,
            "base6_digit_roots": {
                str(key): value for key, value in sorted(BASE6_DIGIT_ROOTS.items())
            },
            "base6_number_words": dict(sorted(BASE6_NUMBER_WORDS.items())),
            "math_operator_roots": dict(sorted(MATH_OPERATOR_ROOTS.items())),
            "english_math_operators": dict(sorted(ENGLISH_MATH_OPERATORS.items())),
        },
        "normalization": {
            "contractions": dict(sorted(ENGLISH_CONTRACTIONS.items())),
            "sentence_final_temporals": dict(sorted(SENTENCE_FINAL_TEMPORALS.items())),
        },
        "reverse": {
            "preferred": dict(sorted(REVERSE_PREFERRED.items())),
            "pronouns": {
                root: dict(sorted(forms.items()))
                for root, forms in sorted(REVERSE_PRONOUNS.items())
            },
            "temporal_glosses": dict(sorted(TEMPORAL_GLOSSES.items())),
        },
        "part_of_speech": {
            "controlled_vocabulary": sorted(PARTS_OF_SPEECH),
            "browser_codes": dict(sorted(PART_OF_SPEECH_BROWSER_CODES.items())),
        },
    }


def runtime_json(grammar: GrammarConfig = DEFAULT_GRAMMAR) -> str:
    """Serialize the shared contract reproducibly with one trailing newline."""
    return json.dumps(
        build_runtime_contract(grammar),
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ) + "\n"


def _runtime_check_resource():
    """Use the checkout artifact when present, otherwise packaged data."""
    return generated_runtime_path() if resolve_repo_root() is not None else PACKAGED_RUNTIME


def check_runtime_export(path: Optional[Union[str, Path]] = None) -> str:
    """Validate one generated contract against the current Python tables."""
    resource = Path(path).expanduser().resolve() if path is not None else _runtime_check_resource()
    try:
        actual = json.loads(resource.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read runtime contract {resource}: {exc}") from exc
    expected = build_runtime_contract()
    if actual != expected:
        raise ValueError(f"{resource} is out of date")
    return str(resource)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def sync_runtime_exports(
    *,
    include_site: bool = False,
    site_root: Optional[Union[str, Path]] = None,
) -> list[Path]:
    """Write package/repository outputs and optional nyx-site copies.

    Synchronization is deliberately source-checkout-only.  Installed wheels
    can print and check the packaged contract but never rewrite site-packages.
    """
    repo_root = resolve_repo_root()
    if repo_root is None:
        raise RuntimeError(
            "runtime synchronization is source-checkout-only; set "
            "XENARI_REPO_ROOT to an explicit checkout"
        )
    paths = [generated_runtime_path()]
    if include_site:
        site = resolve_site_root(site_root)
        paths.extend(
            [
                site / "src" / "data" / "xenari-runtime.json",
                site / "public" / "xenari-runtime-data.json",
            ]
        )

    text = runtime_json()
    for path in paths:
        _write_text_atomic(path, text)
    return paths
