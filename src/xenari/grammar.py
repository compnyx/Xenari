"""Immutable canonical grammar particles and reviewed English mappings."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, TypeVar

PronounSpec = tuple[str, bool] | tuple[str, bool, bool]
_K = TypeVar("_K")
_V = TypeVar("_V")


def _immutable(values: Mapping[_K, _V]) -> Mapping[_K, _V]:
    """Copy a mapping into a read-only view owned by the grammar config."""
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class GrammarConfig:
    """All grammar tables required by the translator.

    A facade receives one explicit config object instead of having module code
    attach a collection of unrelated attributes at runtime. Mapping values are
    copied into read-only views and word collections use ``frozenset`` so the
    frozen dataclass is deeply immutable for the supported value types.
    """

    particles: Mapping[str, str]
    pronouns: Mapping[str, str]
    english_pronouns: Mapping[str, PronounSpec]
    tense_roots: Mapping[str, str]
    evidential_roots: Mapping[str, str]
    verb_roots: Mapping[str, str]
    copula_words: frozenset[str]
    skip_words: frozenset[str]

    def to_runtime_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable browser/tool contract."""
        return {
            "particles": dict(sorted(self.particles.items())),
            "pronouns": dict(sorted(self.pronouns.items())),
            "english_pronouns": {
                key: list(value)
                for key, value in sorted(self.english_pronouns.items())
            },
            "tense_roots": dict(sorted(self.tense_roots.items())),
            "evidential_roots": dict(sorted(self.evidential_roots.items())),
            "verb_roots": dict(sorted(self.verb_roots.items())),
            "copula_words": sorted(self.copula_words),
            "skip_words": sorted(self.skip_words),
        }


def _build_default_config() -> GrammarConfig:
    """Build the shared, immutable default grammar configuration."""
    # Particles from spec §2.3
    particles = {
        "subj": "ka", "obj": "ra", "verb": "ta", "loc": "na", "goal": "fa",
        "inst": "mo", "anim": "vi", "inan": "nu",
        "past": "lo", "fut": "ve", "pres": "sa", "hab": "du", "pot": "pe", "imp": "ko",
        "wit": "xa", "infr": "xe", "rep": "xi", "assum": "xo", "mir": "zu",
        "neg": "ngu", "foc": "pli", "conc": "truq", "q": "va",
        "sub": "su", "endsub": "ti", "pl": "ha", "poss": "po",
        "and": "xen", "or": "noq", "but": "kex",
    }

    # Ordinal pronouns (spec §2.4). The numeric keys match the canon
    # ordinal labels so English mappings cannot silently swap readings.
    pronouns = {
        "1": "neq",   # I/me
        "2": "mex",   # you
        "3": "leq",   # present other
        "4": "req",   # absent known other
        "5": "seq",   # unknown/foreign other
        "6": "zeq",   # indefinite/abstract other
    }

    # English does not encode Xenari ordinal context. Bare they/them/their
    # default to plural known others (req ha), never inferred zeq.
    english_pronouns: dict[str, PronounSpec] = {
        "i": ("1", False), "me": ("1", False), "my": ("1", True), "mine": ("1", True),
        "we": ("1", False, True), "us": ("1", False, True), "our": ("1", True, True),
        "you": ("2", False), "your": ("2", True), "yours": ("2", True),
        "he": ("3", False), "him": ("3", False), "his": ("3", True),
        "she": ("3", False), "her": ("3", False), "hers": ("3", True),
        "it": ("3", False), "its": ("3", True),
        "they": ("4", False, True), "them": ("4", False, True),
        "their": ("4", True, True), "theirs": ("4", True, True),
    }

    tense_roots = {
        "pres": "sa", "present": "sa",
        "past": "lo", "ed": "lo", "was": "lo", "were": "lo", "had": "lo", "did": "lo",
        "future": "ve", "will": "ve", "shall": "ve", "would": "ve",
        "habitual": "du", "usually": "du", "often": "du", "always": "du",
        "potential": "pe", "could": "pe", "might": "pe", "may": "pe",
        "imperative": "ko",
    }

    evidential_roots = {
        "witnessed": "xa", "saw": "xa",
        "inferred": "xe",
        "reported": "xi", "heard": "xi",
        "assumed": "xo",
        "mirative": "zu", "surprise": "zu",
    }

    # Common English verbs that exist in the lexicon
    # We check these against the lexicon at runtime
    # English -> Xenari verb roots (from actual lexicon)
    verb_roots = {
        "want": "glemp", "desire": "glemp",
        "wants": "glemp", "wanted": "glemp",
        "love": "zrent", "loved": "zrent",
        "loves": "zrent",
        "fuck": "qroz",
        "fucks": "qroz",
        "fucking": "qroz",
        "need": "qemp",
        "needs": "qemp",
        "needed": "qemp",
        "have": "xrong",
        "has": "xrong",
        "had": "xrong",
        "eat": "xlof",
        "eats": "xlof",
        "ate": "xlof",
        "go": "qeng",
        "goes": "qeng",
        "going": "qeng",
        "went": "qeng",
        "approach": "frig",
        "approaches": "frig",
        "approached": "frig",
        "blow": "qruq",
        "blows": "qruq",
        "blew": "qruq",
        "blown": "qruq",
        "come": "di",
        "comes": "di",
        "came": "di",
        "run": "zaqa",
        "runs": "zaqa",
        "ran": "zaqa",
        "walk": "kroc",
        "walks": "kroc",
        "walked": "kroc",
        "fall": "hup",
        "falls": "hup",
        "fell": "hup",
        "stop": "semax",
        "stops": "semax",
        "stopped": "semax",
        "start": "qe",
        "starts": "qe",
        "started": "qe",
        "bite": "qruq'",
        "bites": "qruq'",
        "bit": "qruq'",
        "say": "krimp",
        "says": "krimp",
        "said": "krimp",
        "tell": "slimp",
        "tells": "slimp",
        "told": "slimp",
        "cook": "krol",
        "fix": "mlun",
        "build": "mrob",
        "built": "mrob",
        "teach": "nyec",
        "learn": "qlef",
        "drink": "qlup",
        "know": "quh",
        "find": "trek",
        "finds": "trek",
        "found": "trek",
        "destroy": "sri",
        "lose": "tric",
        "pull": "xram",
        "push": "hrag",
        "hide": "co",
        "open": "xleq",
        "opens": "xleq",
        "opened": "xleq",
        "close": "qrak",
        "make": "qlemp",
        "shape": "qlemp",
        "grow": "qlax",
        "break": "zont",
        "broke": "zont",
        "broken": "zont",
        "dream": "qax",
        "think": "bre",
        "change": "xreq",
        "ask": "prant",
        "write": "vlex",
        "inscribe": "vlex",
        "roleplay": "frez",
        "pretend": "frez",
        "submit": "prad",
        "yield": "prad",
        "kiss": "nquxe",
        "kisses": "nquxe",
        "kissed": "nquxe",
        "see": "toq",
        "sees": "toq",
        "seeing": "toq",
        "saw": "toq",
        "seen": "toq",
        "look": "toq",
        "looks": "toq",
        "looked": "toq",
        "watch": "toq",
        "watches": "toq",
        "watched": "toq",
        "hear": "cromq",
        "hears": "cromq",
        "heard": "cromq",
        "listen": "grip",
        "listens": "grip",
        "whisper": "tyequga",
        "whispers": "tyequga",
        "whispered": "tyequga",
        "speak": "zuqra",
        "speaks": "zuqra",
        "spoke": "zuqra",
        "talk": "zuqra",
        "talks": "zuqra",
        "sleep": "pramx",
        "sleeps": "pramx",
        "slept": "pramx",
        "rest": "ezlolax",
        "rests": "ezlolax",
        "rested": "ezlolax",
        "kill": "sri",
        "send": "bern",
        "sends": "bern",
        "sent": "bern",
        "give": "flux",
        "gives": "flux",
        "gave": "flux",
        "given": "flux",
        "take": "treq",
        "takes": "treq",
        "took": "treq",
        "taken": "treq",
        "put": "xlom",
        "sit": "bezli",
        "sits": "bezli",
        "sat": "bezli",
        "stand": "cirku",
        "stands": "cirku",
        "stood": "cirku",
        "touch": "qabrerd",
        "touched": "qabrerd",
        "slam": "tulo",
        "slammed": "tulo",
        "wait": "trekq",
        "help": "pegzos",
        "helps": "pegzos",
        "helped": "pegzos",
        "hurt": "zont",
        "burn": "xraq",
        "work": "qxundraz",
        "works": "qxundraz",
        "worked": "qxundraz",
        "working": "qxundraz",
        "operate": "qxundraz",
        "operates": "qxundraz",
        "operated": "qxundraz",
        "operating": "qxundraz",
        "throw": "qranx",
        "throws": "qranx",
        "throwing": "qranx",
        "threw": "qranx",
        "thrown": "qranx",
        "decode": "nimixu",
        "decodes": "nimixu",
        "decoded": "nimixu",
        "decoding": "nimixu",
        "decipher": "nimixu",
        "deciphers": "nimixu",
        "deciphered": "nimixu",
        "deciphering": "nimixu",
        "translate": "nrotm",
        "translates": "nrotm",
        "translated": "nrotm",
        "translating": "nrotm",
        "enter": "logi",
        "enters": "logi",
        "entered": "logi",
        "belong": "mifzxuri",
        "belongs": "mifzxuri",
        "belonged": "mifzxuri",
        "get": "smite",
        "gets": "smite",
        "got": "smite",
        "gotten": "smite",
        "getting": "smite",
    }

    copula_words = {"is", "are", "am", "be", "was", "were", "being", "feel"}

    # English function words to skip (not nouns, not verbs)
    skip_words = {"the", "a", "an", "to", "of", "in", "on", "at", "by", "for",
                  "with", "from", "as", "that", "this", "these", "those",
                  "it", "its", "so", "very", "just", "really", "also",
                  "about", "into", "through", "during", "before", "after",
                  "above", "below", "up", "down", "out", "over", "under",
                  "again", "further", "then", "once", "here", "there",
                  "all", "any", "both", "each", "few", "more", "most",
                  "other", "some", "such", "only", "own", "same", "than",
                  "too", "s", "t", "can", "should", "now", "today",
                  "yesterday", "tomorrow", "tonight"}

    return GrammarConfig(
        particles=_immutable(particles),
        pronouns=_immutable(pronouns),
        english_pronouns=_immutable(english_pronouns),
        tense_roots=_immutable(tense_roots),
        evidential_roots=_immutable(evidential_roots),
        verb_roots=_immutable(verb_roots),
        copula_words=frozenset(copula_words),
        skip_words=frozenset(skip_words),
    )


DEFAULT_GRAMMAR = _build_default_config()
