"""Reviewed translation tables shared by Python and browser runtimes.

The browser contract is generated from these values; consumers should not
maintain hand-copied versions.  Read-only mappings make accidental mutation
during a translation impossible while preserving ordinary mapping semantics.
"""

from types import MappingProxyType
from typing import Mapping, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")

BASE6_PLACE_ROOT = "xang"


def _immutable(values: Mapping[_K, _V]) -> Mapping[_K, _V]:
    return MappingProxyType(dict(values))


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
        "fatyih": "dangerous",
        "qex": "alien",
        "loco": "figure",
        "qlon": "lake",
        "brid": "hat",
        "cuq": "wind",
        "qruq": "blow",
        "frig": "approach",
        "rlis": "red",
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
        "shengtac": "problem",
    }
)
