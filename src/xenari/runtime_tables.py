"""Reviewed translation tables shared by Python and browser runtimes.

The browser contract is generated from these values; consumers should not
maintain hand-copied versions.  Read-only mappings make accidental mutation
during a translation impossible while preserving ordinary mapping semantics.
"""

import json
from importlib.resources import files
from types import MappingProxyType
from typing import Mapping, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")

BASE6_PLACE_ROOT = "xang"


def _immutable(values: Mapping[_K, _V]) -> Mapping[_K, _V]:
    return MappingProxyType(dict(values))


def _load_v4_preferences() -> dict[str, object]:
    """Load the generated full-lexicon preference layer when packaged."""
    resource = files("xenari").joinpath("data").joinpath("common-english-pos-v4.json")
    try:
        payload = json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # The source tree can build the runtime architecture before the final
        # atomic curation fixture is generated. Packaging tests require the
        # resource once v4 ships.
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load common-English POS v4 preferences: {exc}") from exc
    if payload.get("schema") != "xenari.common-english-pos.v4":
        raise RuntimeError("common-English POS v4 fixture has an unsupported schema")
    preferences = payload.get("preferences")
    if not isinstance(preferences, dict):
        raise RuntimeError("common-English POS v4 fixture is missing preferences")
    return preferences


def _load_post_v4_mappings() -> list[dict[str, object]]:
    """Load reviewed lexical preferences added after the frozen v4 pass."""
    resource = files("xenari").joinpath("data").joinpath("post-v4-lexicon-v1.json")
    try:
        payload = json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load post-v4 lexical preferences: {exc}") from exc
    if payload.get("schema") != "xenari.post-v4-lexicon.v1":
        raise RuntimeError("post-v4 lexicon fixture has an unsupported schema")
    mappings = payload.get("mappings")
    if not isinstance(mappings, list):
        raise RuntimeError("post-v4 lexicon fixture is missing mappings")
    reviewed = []
    seen_roots = set()
    seen_keys = set()
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            raise RuntimeError(f"post-v4 mapping {index} must be an object")
        english_key = mapping.get("english_key")
        root = mapping.get("root")
        part_of_speech = mapping.get("part_of_speech")
        kind = mapping.get("kind")
        if any(not isinstance(value, str) or not value for value in (
            english_key, root, part_of_speech, kind
        )):
            raise RuntimeError(
                f"post-v4 mapping {index} requires non-empty string fields"
            )
        if part_of_speech not in {"noun", "verb"}:
            raise RuntimeError(
                f"post-v4 mapping {english_key!r} has unsupported POS {part_of_speech!r}"
            )
        inflections = mapping.get("inflections")
        if part_of_speech == "verb" and (
            not isinstance(inflections, dict)
            or any(
                not isinstance(inflections.get(key), str)
                or not inflections.get(key)
                for key in ("past", "third_person")
            )
        ):
            raise RuntimeError(
                f"post-v4 verb mapping {english_key!r} requires reviewed inflections"
            )
        if root in seen_roots or english_key in seen_keys:
            raise RuntimeError("post-v4 lexical preferences must be one-to-one")
        seen_roots.add(root)
        seen_keys.add(english_key)
        reviewed_mapping = {
            "english_key": english_key,
            "root": root,
            "part_of_speech": part_of_speech,
            "kind": kind,
        }
        if inflections is not None:
            reviewed_mapping["inflections"] = dict(inflections)
        reviewed.append(reviewed_mapping)
    return reviewed


def _string_map(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise RuntimeError(f"common-English POS v4 {label} must be an object")
    if any(
        not isinstance(key, str)
        or not key
        or not isinstance(item, str)
        or not item
        for key, item in value.items()
    ):
        raise RuntimeError(
            f"common-English POS v4 {label} must map non-empty strings"
        )
    return dict(value)


def _nested_string_maps(value: object, label: str) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        raise RuntimeError(f"common-English POS v4 {label} must be an object")
    return {
        key: _string_map(item, f"{label}.{key}") for key, item in value.items()
    }


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise RuntimeError(
            f"common-English POS v4 {label} must be an array of non-empty strings"
        )
    if len(value) != len(set(value)):
        raise RuntimeError(f"common-English POS v4 {label} must not contain duplicates")
    return list(value)


BASE6_DIGIT_ROOTS: Mapping[int, str] = _immutable(
    {
        0: "nul",
        1: "ca",
        2: "vriq",
        3: "prit",
        4: "qang",
        5: "cum",
    }
)

BASE6_NUMBER_WORDS: Mapping[str, int] = _immutable(
    {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }
)

MATH_OPERATOR_ROOTS: Mapping[str, str] = _immutable(
    {
        "plus": "plomt",
        "add": "plomt",
        "added to": "plomt",
        "addition": "plomt",
        "minus": "krut",
        "subtract": "krut",
        "subtracted by": "krut",
        "subtraction": "krut",
        "times": "vrot",
        "multiply": "vrot",
        "multiplied by": "vrot",
        "grouped by": "vrot",
        "divided by": "flopq",
        "divide by": "flopq",
        "divide": "flopq",
        "split by": "flopq",
        "equals": "zlem",
        "equal to": "zlem",
        "same as": "zlem",
        "greater than": "grak",
        "more than": "grak",
        "less than": "vlox",
        "fewer than": "vlox",
        "fraction": "nok",
        "ratio": "nok",
        "over": "nok",
        "+": "plomt",
        "-": "krut",
        "*": "vrot",
        "x": "vrot",
        "×": "vrot",
        "/": "flopq",
        "=": "zlem",
        ">": "grak",
        "<": "vlox",
    }
)

ENGLISH_MATH_OPERATORS: Mapping[str, str] = _immutable(
    {
        "plomt": "plus",
        "krut": "minus",
        "vrot": "times",
        "flopq": "divided by",
        "zlem": "equals",
        "grak": "greater than",
        "vlox": "less than",
        "nok": "fraction",
    }
)

ENGLISH_CONTRACTIONS: Mapping[str, str] = _immutable(
    {
        "i'm": "i am",
        "i've": "i have",
        "i'll": "i will",
        "i'd": "i would",
        "you're": "you are",
        "you've": "you have",
        "you'll": "you will",
        "you'd": "you would",
        "we're": "we are",
        "we've": "we have",
        "we'll": "we will",
        "we'd": "we would",
        "they're": "they are",
        "they've": "they have",
        "they'll": "they will",
        "they'd": "they would",
        "he's": "he is",
        "she's": "she is",
        "it's": "it is",
        "that's": "that is",
        "he'll": "he will",
        "she'll": "she will",
        "he'd": "he would",
        "she'd": "she would",
        "what's": "what is",
        "who's": "who is",
        "how's": "how is",
        "how're": "how are",
        "isn't": "is not",
        "aren't": "are not",
        "wasn't": "was not",
        "weren't": "were not",
        "don't": "do not",
        "doesn't": "does not",
        "didn't": "did not",
        "won't": "will not",
        "can't": "can not",
        "cannot": "can not",
        "wouldn't": "would not",
        "couldn't": "could not",
        "shouldn't": "should not",
        "mustn't": "must not",
        "haven't": "have not",
        "hasn't": "has not",
        "hadn't": "had not",
        "let's": "let us",
        "y'all": "you all",
        "gonna": "going to",
        "wanna": "want to",
        "gotta": "got to",
        "kinda": "kind of",
        "sorta": "sort of",
    }
)

SENTENCE_FINAL_TEMPORALS: Mapping[str, str] = _immutable(
    {
        "today": "bro",
        "tomorrow": "glent",
        "yesterday": "hreh",
        "tonight": "kohfrep",
    }
)

TEMPORAL_GLOSSES: Mapping[str, str] = _immutable(
    {
        "bro": "today",
        "glent": "tomorrow",
        "hreh": "yesterday",
        "kohfrep": "tonight",
        "qros": "now",
        "qrosa": "now",
    }
)

# Default lexical selection is independent of POS.  Every colliding English
# key can name several intentional senses, while ordinary context-free lookup
# still needs one deterministic root.
FORWARD_PREFERRED: Mapping[str, str] = _immutable(
    {
        "language": "zuqra",
    }
)

# POS-aware lexical selection resolves collisions within one reviewed part of
# speech.  Values are populated by the complete common-English curation
# fixture; keeping this table distinct prevents translation-role preferences
# from pretending that a mapping exists on the selected root.
LOOKUP_PREFERRED_BY_PART_OF_SPEECH: Mapping[str, Mapping[str, str]] = (
    MappingProxyType({})
)

# English keys can name an intentional canonical sense without being the
# translator's unmarked reading.  Keep selection separate from POS: POS says
# that ``clutching -> roqni`` is a verb sense, while this table preserves the
# established sentence-translation root ``xrics`` for bare "clutching".
TRANSLATION_PREFERRED_BY_PART_OF_SPEECH: Mapping[str, Mapping[str, str]] = (
    MappingProxyType(
        {
            "verb": _immutable(
                {
                    "clutching": "xrics",
                    "colliding": "pyeqesit",
                    "deserves": "znunz",
                    "digging": "sfeksixm",
                    "dragging": "mozfuka",
                    "flexing": "funx",
                    "gaining": "smite",
                    "grabbing": "tingk",
                    "kicked": "kite",
                    "kicking": "kite",
                    "mounting": "rurics",
                    "operating": "qxundraz",
                    "proceeds": "norklamz",
                    "sent": "bern",
                    "translating": "nrotm",
                    "wrapping": "zuyur",
                }
            ),
        }
    )
)

# Compatibility name for callers of the schema-v2 runtime table.  New code
# should say whether it wants lexical or translation-role selection.
FORWARD_PREFERRED_BY_PART_OF_SPEECH = TRANSLATION_PREFERRED_BY_PART_OF_SPEECH

REVERSE_PRONOUNS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "neq": _immutable({"subj": "I", "obj": "me", "poss": "my"}),
        "mex": _immutable({"subj": "you", "obj": "you", "poss": "your"}),
        "leq": _immutable(
            {"subj": "he/she/it", "obj": "him/her/it", "poss": "his/her/its"}
        ),
        "req": _immutable({"subj": "they", "obj": "them", "poss": "their"}),
        "seq": _immutable(
            {"subj": "stranger", "obj": "stranger", "poss": "stranger's"}
        ),
        "zeq": _immutable({"subj": "they", "obj": "them", "poss": "their"}),
    }
)

REVERSE_PREFERRED: Mapping[str, str] = _immutable(
    {
        "zrent": "love",
        "toq": "see",
        "zux": "is",
        "qrazhel": "retard",
        "fatyih": "dangerous",
        "qex": "alien",
        "loco": "figure",
        "qlon": "lake",
        "brid": "hat",
        "cuq": "wind",
        "qruq": "blow",
        "frig": "approach",
        "rlis": "red",
        "tre": "grey",
        "qeng": "go",
        "qxundraz": "operate",
        "kashatyong": "job",
        "qzecmru": "anyway",
        "qranx": "throw",
        "flonx": "art",
        "hune": "sentence",
        "fona": "translator",
        "halbru": "reverse-engineer",
        "smite": "get",
        "duqe": "result",
        "naxru": "please",
        "mrob": "build",
        "krimp": "say",
        "qabrerd": "touch",
        "tulo": "slam",
        "semax": "stop",
        "zont": "break",
        "xlonqtoq": "window",
        "trekq": "wait",
        "spokta": "elevator",
        "zrump": "door",
        "qroxang": "there",
        "zaqa": "run",
        "xleq": "open",
        "logi": "enter",
        "pegzos": "help",
        "trek": "find",
        "nrotm": "translate",
        "mifzxuri": "belong",
        "kazxibrih": "woman",
        "zrenq": "dog",
        "habdazluc": "person",
        "pronx": "tool",
        "cruq": "water",
        "canq": "forest",
        "qruq'": "bite",
        "tyequga": "whisper",
        "stux": "ok",
        "naxq": "yes",
        "naxu": "nice",
        "bivuzqa": "humanity",
        "uqel": "planet",
        "zuqra": "voice",
        "qlox'": "goodbye",
        "vreqclir": "understood",
        "gral": "thanks",
        "qezxol": "sorry",
        "vrin": "whoops",
        "vroq": "yeah",
        "nguq": "no",
        "vex": "maybe",
        "mse": "much",
        "vehya": "potato",
        "shengtac": "problem",
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
)

# Raw reverse preferences preserve the bijective display key. Grammatical
# slots select a separately reviewed surface for the root's requested POS;
# verbs, for example, use a lemma while nouns retain intentional lexical
# number. The v4 fixture replaces this empty bootstrap table in releases.
REVERSE_PREFERRED_BY_PART_OF_SPEECH: Mapping[str, Mapping[str, str]] = (
    MappingProxyType({})
)

# Noun role heads that already carry plural or invariant number. An explicit
# Xenari `ha` is idempotent for these roots instead of producing `facilitieses`.
REVERSE_PLURAL_NOUN_ROOTS: frozenset[str] = frozenset()

# Full reviewed finite phrases for every v4 verb-role root. Keeping these in
# the shared contract prevents Python and browser runtimes from maintaining
# separate heuristic English conjugators.
REVERSE_VERB_INFLECTIONS: Mapping[str, Mapping[str, str]] = MappingProxyType({})


_V4_PREFERENCES = _load_v4_preferences()
if _V4_PREFERENCES:
    _v4_forward = _V4_PREFERENCES.get("forward")
    _v4_reverse = _V4_PREFERENCES.get("reverse")
    if not isinstance(_v4_forward, dict) or not isinstance(_v4_reverse, dict):
        raise RuntimeError(
            "common-English POS v4 preferences require forward and reverse objects"
        )

    FORWARD_PREFERRED = _immutable(
        {
            **FORWARD_PREFERRED,
            **_string_map(_v4_forward.get("preferred"), "forward.preferred"),
        }
    )

    _lookup_preferences = _nested_string_maps(
        _v4_forward.get("lookup_preferred_by_part_of_speech"),
        "forward.lookup_preferred_by_part_of_speech",
    )
    LOOKUP_PREFERRED_BY_PART_OF_SPEECH = MappingProxyType(
        {
            part_of_speech: _immutable(preferences)
            for part_of_speech, preferences in _lookup_preferences.items()
        }
    )

    _translation_preferences = {
        part_of_speech: dict(preferences)
        for part_of_speech, preferences in (
            TRANSLATION_PREFERRED_BY_PART_OF_SPEECH.items()
        )
    }
    for part_of_speech, preferences in _nested_string_maps(
        _v4_forward.get("translation_preferred_by_part_of_speech"),
        "forward.translation_preferred_by_part_of_speech",
    ).items():
        _translation_preferences.setdefault(part_of_speech, {}).update(preferences)
    TRANSLATION_PREFERRED_BY_PART_OF_SPEECH = MappingProxyType(
        {
            part_of_speech: _immutable(preferences)
            for part_of_speech, preferences in _translation_preferences.items()
        }
    )

    REVERSE_PREFERRED = _immutable(
        {
            **REVERSE_PREFERRED,
            **_string_map(_v4_reverse.get("preferred"), "reverse.preferred"),
        }
    )

    _reverse_role_preferences = _nested_string_maps(
        _v4_reverse.get("preferred_by_part_of_speech"),
        "reverse.preferred_by_part_of_speech",
    )
    REVERSE_PREFERRED_BY_PART_OF_SPEECH = MappingProxyType(
        {
            part_of_speech: _immutable(preferences)
            for part_of_speech, preferences in _reverse_role_preferences.items()
        }
    )
    REVERSE_PLURAL_NOUN_ROOTS = frozenset(
        _string_list(
            _v4_reverse.get("plural_noun_roots"),
            "reverse.plural_noun_roots",
        )
    )
    _reverse_verb_inflections = _nested_string_maps(
        _v4_reverse.get("verb_inflections"),
        "reverse.verb_inflections",
    )
    for root, forms in _reverse_verb_inflections.items():
        if set(forms) != {"past", "third_person"}:
            raise RuntimeError(
                f"common-English POS v4 reverse.verb_inflections.{root} "
                "must contain exactly past and third_person"
            )
    REVERSE_VERB_INFLECTIONS = MappingProxyType(
        {
            root: _immutable(forms)
            for root, forms in _reverse_verb_inflections.items()
        }
    )


_POST_V4_MAPPINGS = _load_post_v4_mappings()
if _POST_V4_MAPPINGS:
    _post_v4_reverse = dict(REVERSE_PREFERRED)
    _post_v4_reverse_roles = {
        part_of_speech: dict(preferences)
        for part_of_speech, preferences in REVERSE_PREFERRED_BY_PART_OF_SPEECH.items()
    }
    _post_v4_verb_inflections = {
        root: dict(forms) for root, forms in REVERSE_VERB_INFLECTIONS.items()
    }
    for mapping in _POST_V4_MAPPINGS:
        english_key = mapping["english_key"]
        root = mapping["root"]
        part_of_speech = mapping["part_of_speech"]
        existing = _post_v4_reverse.get(root)
        if existing is not None and existing != english_key:
            raise RuntimeError(
                f"post-v4 reverse preference conflicts for {root!r}: "
                f"{existing!r} != {english_key!r}"
            )
        role_preferences = _post_v4_reverse_roles.setdefault(part_of_speech, {})
        existing_role = role_preferences.get(root)
        if existing_role is not None and existing_role != english_key:
            raise RuntimeError(
                f"post-v4 reverse role preference conflicts for {root!r}: "
                f"{existing_role!r} != {english_key!r}"
            )
        _post_v4_reverse[root] = english_key
        role_preferences[root] = english_key
        if part_of_speech == "verb":
            inflections = mapping["inflections"]
            existing_inflections = _post_v4_verb_inflections.get(root)
            if existing_inflections is not None and existing_inflections != inflections:
                raise RuntimeError(
                    f"post-v4 verb inflections conflict for {root!r}"
                )
            _post_v4_verb_inflections[root] = dict(inflections)
    REVERSE_PREFERRED = _immutable(_post_v4_reverse)
    REVERSE_PREFERRED_BY_PART_OF_SPEECH = MappingProxyType(
        {
            part_of_speech: _immutable(preferences)
            for part_of_speech, preferences in _post_v4_reverse_roles.items()
        }
    )
    REVERSE_VERB_INFLECTIONS = MappingProxyType(
        {
            root: _immutable(forms)
            for root, forms in _post_v4_verb_inflections.items()
        }
    )

# Compatibility name must follow the optional v4 merge.
FORWARD_PREFERRED_BY_PART_OF_SPEECH = TRANSLATION_PREFERRED_BY_PART_OF_SPEECH
