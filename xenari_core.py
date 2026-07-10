#!/usr/bin/env python3
"""Core Xenari facade assembled from focused tool mixins."""

from pathlib import Path
from typing import Dict, Optional

from xenari_export import ExportMixin
from xenari_health import HealthMixin
from xenari_lookup import LookupMixin
from xenari_mutation import MutationMixin
from xenari_translate import TranslatorMixin


class Xenari(LookupMixin, TranslatorMixin, ExportMixin, HealthMixin, MutationMixin):
    def __init__(self, db_path: Optional[Path] = None):
        from xenari_db import XenariDB
        self.db = XenariDB(db_path) if db_path else XenariDB()
        self.lexicon: Dict[str, str] = {}          # root -> meaning
        self.english_to_root: Dict[str, str] = {}  # english -> root
        self._load_from_db()

        # Particles from spec §2.3
        self.p = {
            "subj": "ka", "obj": "ra", "verb": "ta", "loc": "na", "goal": "fa",
            "inst": "mo", "anim": "vi", "inan": "nu",
            "past": "lo", "fut": "ve", "pres": "sa", "hab": "du", "pot": "pe", "imp": "ko",
            "wit": "xa", "infr": "xe", "rep": "xi", "assum": "xo", "mir": "zu",
            "neg": "ngu", "foc": "pli", "conc": "truq", "q": "va",
            "sub": "su", "endsub": "ti", "pl": "ha", "poss": "po",
            "and": "xen", "or": "noq", "but": "kex",
        }

        # Ordinal pronouns (spec §2.4)
        self.pronouns = {
            "1": "neq",   # I/me
            "2": "mex",   # you
            "3": "zeq",   # indefinite/abstract other
            "4": "leq",   # present third person
        }

        # English pronoun mapping
        self.en_pronouns = {
            "i": ("1", False), "me": ("1", False), "my": ("1", True), "mine": ("1", True),
            "we": ("1", False, True), "us": ("1", False, True), "our": ("1", True, True),
            "you": ("2", False), "your": ("2", True), "yours": ("2", True),
            "he": ("4", False), "him": ("4", False), "his": ("4", True),
            "she": ("4", False), "her": ("4", False), "hers": ("4", True),
            "it": ("4", False), "its": ("4", True),
            "they": ("3", False), "them": ("3", False), "their": ("3", True), "theirs": ("3", True),
        }

        self.tense_map = {
            "pres": "sa", "present": "sa",
            "past": "lo", "ed": "lo", "was": "lo", "were": "lo", "had": "lo", "did": "lo",
            "future": "ve", "will": "ve", "shall": "ve", "would": "ve",
            "habitual": "du", "usually": "du", "often": "du", "always": "du",
            "potential": "pe", "could": "pe", "might": "pe", "may": "pe",
            "imperative": "ko",
        }

        self.evidential_map = {
            "witnessed": "xa", "saw": "xa",
            "inferred": "xe",
            "reported": "xi", "heard": "xi",
            "assumed": "xo",
            "mirative": "zu", "surprise": "zu",
        }

        # Common English verbs that exist in the lexicon
        # We check these against the lexicon at runtime
        # English -> Xenari verb roots (from actual lexicon)
        self.verb_map = {
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
            "eat": "xlof",
            "eats": "xlof",
            "ate": "xlof",
            "go": "qeng",
            "goes": "qeng",
            "going": "qeng",
            "went": "qeng",
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
            "need": "qemp",
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
            "speak": "zuqra",
            "speaks": "zuqra",
            "spoke": "zuqra",
            "talk": "zuqra",
            "talks": "zuqra",
            "sleep": "qax",
            "sleeps": "qax",
            "rest": "qax",
            "kill": "sri",
            "live": "ngol",
            "send": "qlax",
            "give": "qlemp",
            "take": "rlenq",
            "get": "rlenq",
            "put": "xlom",
            "sit": "hup",
            "stand": "kroc",
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

        self.copula_words = {"is", "are", "am", "be", "was", "were", "being", "feel"}

        # English function words to skip (not nouns, not verbs)
        self.skip_words = {"the", "a", "an", "to", "of", "in", "on", "at", "by", "for",
                           "with", "from", "as", "that", "this", "these", "those",
                           "it", "its", "so", "very", "just", "really", "also",
                           "about", "into", "through", "during", "before", "after",
                           "above", "below", "up", "down", "out", "over", "under",
                           "again", "further", "then", "once", "here", "there",
                           "all", "any", "both", "each", "few", "more", "most",
                           "other", "some", "such", "only", "own", "same", "than",
                           "too", "s", "t", "can", "should", "now", "today",
                           "yesterday", "tomorrow", "tonight"}

    def _load_from_db(self):
        """Load all roots and english mappings from the sqlite DB."""
        for row in self.db.conn.execute("SELECT root, meaning FROM roots"):
            self.lexicon[row["root"]] = row["meaning"].lower()
        for row in self.db.conn.execute("SELECT english_key, root, context_note FROM english_map JOIN roots ON roots.id = english_map.root_id"):
            key = row["english_key"].lower()
            if key not in self.english_to_root:
                self.english_to_root[key] = row["root"]
            else:
                current = self.english_to_root[key]
                current_score = self.db._lookup_score(key, self.lexicon.get(current, ""))
                candidate_score = self.db._lookup_score(key, self.lexicon.get(row["root"], ""), row["context_note"])
                if candidate_score > current_score:
                    self.english_to_root[key] = row["root"]
