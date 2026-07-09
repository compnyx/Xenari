#!/usr/bin/env python3
"""
Xenari Tool v3 — for Nyx to speak Xenari properly.
Strict: only real roots, no hallucinations. Unknown words marked clearly.

Usage:
  python xenari_tool.py lookup "big"
  python xenari_tool.py compound big daddy
  python xenari_tool.py speak "I want big daddy" --tense pres --evidential witnessed
  python xenari_tool.py speak "you are cute" --evidential inferred
  python xenari_tool.py gloss "fuck it we ball"
  python xenari_tool.py export-js

Import:
  from xenari_tool import Xenari
  x = Xenari()
  x.speak("I love you", tense="pres", evidential="witnessed")
"""

import re
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Tuple, List
import datetime


class Xenari:
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
            "3": "zeq",   # they (3rd ordinal)
        }

        # English pronoun mapping
        self.en_pronouns = {
            "i": ("1", False), "me": ("1", False), "my": ("1", True), "mine": ("1", True),
            "we": ("1", False, True), "us": ("1", False, True), "our": ("1", True, True),
            "you": ("2", False), "your": ("2", True), "yours": ("2", True),
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
            "go": "sloz",
            "goes": "sloz",
            "went": "sloz",
            "come": "di",
            "comes": "di",
            "came": "di",
            "run": "drez",
            "runs": "drez",
            "ran": "drez",
            "walk": "kroc",
            "walks": "kroc",
            "walked": "kroc",
            "fall": "hup",
            "falls": "hup",
            "fell": "hup",
            "stop": "kam",
            "stops": "kam",
            "stopped": "kam",
            "start": "qe",
            "starts": "qe",
            "started": "qe",
            "bite": "krap",
            "bites": "krap",
            "bit": "krap",
            "say": "krimp",
            "says": "krimp",
            "said": "krimp",
            "tell": "slimp",
            "tells": "slimp",
            "told": "slimp",
            "cook": "krol",
            "fix": "mlun",
            "build": "mrob",
            "teach": "nyec",
            "learn": "qlef",
            "drink": "qlup",
            "know": "quh",
            "find": "rlenq",
            "destroy": "sri",
            "lose": "tric",
            "pull": "xram",
            "push": "hrag",
            "hide": "co",
            "open": "glag",
            "close": "qrak",
            "make": "qlemp",
            "shape": "qlemp",
            "grow": "qlax",
            "break": "zont",
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
            "kiss": "krap",
            "need": "qemp",
            "see": "toq",
            "sees": "toq",
            "seeing": "toq",
            "saw": "toq",
            "look": "toq",
            "looks": "toq",
            "looked": "toq",
            "watch": "toq",
            "watches": "toq",
            "watched": "toq",
            "hear": "cremp",
            "hears": "cremp",
            "listen": "cremp",
            "listens": "cremp",
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
            "wait": "kam",
            "help": "qlemp",
            "hurt": "zont",
            "burn": "xraq",
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
                           "too", "s", "t", "can", "should", "now"}


    def _load_from_db(self):
        """Load all roots and english mappings from the sqlite DB."""
        for row in self.db.conn.execute("SELECT root, meaning FROM roots"):
            self.lexicon[row["root"]] = row["meaning"].lower()
        for row in self.db.conn.execute("SELECT english_key, root FROM english_map JOIN roots ON roots.id = english_map.root_id"):
            key = row["english_key"].lower()
            if key not in self.english_to_root:
                self.english_to_root[key] = row["root"]

    # === CORE LOOKUP ===

    def lookup(self, english: str) -> Tuple[Optional[str], Optional[str]]:
        """Look up an English word, return (root, meaning) or (None, None)."""
        key = english.lower().strip()
        if key in self.english_to_root:
            root = self.english_to_root[key]
            return root, self.lexicon.get(root, "")
        return None, None

    def lookup_root(self, root: str) -> str:
        """Look up a Xenari root, return its meaning."""
        return self.lexicon.get(root, "unknown root")

    def _safe_root(self, word: str) -> str:
        """Return real root or [unknown:word]. Never hallucinates."""
        root, _ = self.lookup(word)
        return root if root else f"[unknown:{word}]"

    def _is_known(self, word: str) -> bool:
        """Check if a word exists in the lexicon."""
        return word.lower().strip() in self.english_to_root

    def _animacy_for(self, root: str, default: str = "nu") -> str:
        """Best-effort animacy for generated clauses.

        Xenari requires animacy on NPs and verb agreement, but the DB does not
        store animacy as a structured field yet. Pronouns are animate; common
        being/animal/person meanings are treated as animate; everything else
        defaults to inanimate.
        """
        if root in self.pronouns.values():
            return self.p["anim"]
        meaning = self.lexicon.get(root, "").lower()
        animate_cues = (
            "person", "being", "creature", "animal", "stranger", "speaker",
            "addressee", "parent", "child", "sibling", "partner", "friend",
            "enemy", "student", "teacher", "worker", "thief", "robber",
            "demon", "succubus", "human", "body", "soul", "living"
        )
        return self.p["anim"] if any(cue in meaning for cue in animate_cues) else default

    def _is_pronoun_root(self, root: str) -> bool:
        """Xenari pronouns carry inherent animacy and do not print vi/nu."""
        return root in self.pronouns.values()

    # === COMPOUNDING ===

    def compound(self, *english_words: str) -> str:
        """
        Right-headed compounding with ' separator when needed.
        Returns [unknown:word] if any word is missing.
        """
        roots = []
        for w in english_words:
            root, _ = self.lookup(w)
            if root:
                roots.append(root)
            else:
                return f"[unknown:{w}]"

        if not roots:
            return ""
        if len(roots) == 1:
            return roots[0]

        result = roots[0]
        for r in roots[1:]:
            # Insert glottal stop if boundary would create gemination
            if result and result[-1] in "bcdfghjklmnpqrstvwxyz" and r[0] in "bcdfghjklmnpqrstvwxyz":
                result += "'"
            result += r
        return result

    def _try_compound_pair(self, w1: str, w2: str) -> Optional[str]:
        """Try to compound two words. Merge if BOTH words exist individually."""
        r1, _ = self.lookup(w1)
        r2, _ = self.lookup(w2)
        if r1 and r2:
            # Build the compound (right-headed)
            result = r1
            if result[-1] in "bcdfghjklmnpqrstvwxyz" and r2[0] in "bcdfghjklmnpqrstvwxyz":
                result += "'"
            result += r2
            return result
        return None

    # === SENTENCE BUILDER ===

    def speak(self, english: str, tense: str = "auto", evidential: str = "auto") -> str:
        """
        Build an OSV sentence from English input.
        - Detects pronouns, compounds, verbs, objects
        - Only uses real roots
        - Handles tense and evidential particles
        - Handles negation
        - Handles possession (po)
        - Handles plural (ha)
        """
        raw_words = re.findall(r"\b\w+\b", english.lower())
        if not raw_words:
            return ""

        # Phase 1: detect and merge compounds (2-word scan)
        tokens = self._merge_compounds(raw_words)

        # Phase 2: classify tokens
        subj = None
        subj_possessive = False
        subj_plural = False
        obj = None
        obj_possessive = False
        verb = None
        copula = False
        negated = False
        adjectives = []
        question = False
        obj_tokens = []

        for i, tok in enumerate(tokens):
            # Pronoun check
            if tok in self.en_pronouns:
                pinfo = self.en_pronouns[tok]
                ordinal = pinfo[0]
                is_poss = pinfo[1]
                is_plural = len(pinfo) > 2 and pinfo[2]
                if subj is None:
                    subj = self.pronouns[ordinal]
                    subj_possessive = is_poss
                    subj_plural = is_plural
                elif obj is None:
                    # Second pronoun becomes the object
                    obj = self.pronouns[ordinal]
                    obj_possessive = is_poss
                continue

            # Negation
            if tok in ("not", "no", "never", "dont", "doesnt", "didnt", "wont", "cant", "cannot"):
                negated = True
                continue

            # Question words
            if tok in ("what", "who", "where", "when", "why", "how", "which", "whose"):
                question = True
                continue

            # Skip function words (the, a, to, of, in, etc.)
            # BUT handle "to" before verb first (infinitive marker)
            if tok == "to" and i + 1 < len(tokens) and (tokens[i+1] in self.verb_map or self._is_verb_like(tokens[i+1])):
                continue
            if tok in self.skip_words:
                continue

            # Tense detection from English words
            if tense == "auto":
                if tok in ("was", "were", "had", "did", "ed"):
                    tense = "past"
                elif tok in ("will", "shall", "would"):
                    tense = "future"
                elif tok in ("usually", "often", "always"):
                    tense = "habitual"
                elif tok in ("could", "might", "may"):
                    tense = "potential"

            # Evidential detection
            if evidential == "auto":
                if tok in ("saw",):
                    evidential = "witnessed"
                elif tok in ("heard",):
                    evidential = "reported"

            # Verb detection
            if tok in self.verb_map:
                if verb is None:
                    verb = self.verb_map[tok]
                else:
                    # Second verb — could be infinitive complement "want to X"
                    # In xenari, just use the second verb as the main verb
                    # and keep the first as a modal-ish prefix
                    # For now: second verb replaces if first is "want"/"need"
                    if verb in ("glemp", "qemp") and self.verb_map[tok] not in ("glemp", "qemp"):
                        verb = self.verb_map[tok]
                continue
            elif tok in self.copula_words:
                copula = True
                continue
            root, _ = self.lookup(tok)
            if root and self._is_verb_like(tok):
                if verb is None:
                    verb = root
                continue

            # Object / adjective
            if root:
                if subj is not None and verb is not None:
                    if obj is None:
                        obj = root
                    else:
                        obj_tokens.append(root)
                elif subj is not None and verb is None:
                    if self._is_verb_like(tok):
                        verb = root
                    elif obj is None:
                        obj = root
                    else:
                        obj_tokens.append(root)
                else:
                    if obj is None:
                        obj = root
                    else:
                        obj_tokens.append(root)
            else:
                # Might be a pre-built compound from merge step
                if all(c in "abcdefghijklmnopqrstuvwxyz'" for c in tok) and len(tok) > 3:
                    if obj is None:
                        obj = tok
                    else:
                        obj_tokens.append(tok)
                    continue

        # Handle copula: "X is Y" → Y OBJ X SUBJ [copula fallback]
        if copula and obj is not None and verb is None:
            if tense == "auto":
                tense = "pres"

        # Defaults
        if subj is None:
            subj = self.pronouns["1"]
        if verb is None and not copula:
            # No verb found and not copula — maybe obj is actually the verb
            if obj is not None and obj in self.lexicon:
                verb = obj
                obj = None

        # Phase 3: build OSV.
        # Canonical order:
        #   ra [animacy] [object]    ka [animacy] [subject]    ta [verb] [subject animacy] [tense] [evidential]
        # Pronouns are exempt from printed animacy and suppress verb agreement.
        parts = []

        # Object phrase
        if obj:
            obj_anim = self._animacy_for(obj)
            obj_parts = [self.p["obj"]]
            if not self._is_pronoun_root(obj):
                obj_parts.append(obj_anim)
            obj_parts.append(obj)
            if obj_possessive:
                obj_parts.append(self.p["poss"])
            for ot in obj_tokens:
                if ot != obj:
                    obj_parts.append(ot)
            parts.append(" ".join(obj_parts))

        # Subject phrase
        subj_anim = self._animacy_for(subj, default=self.p["anim"])
        subj_parts = [self.p["subj"]]
        if not self._is_pronoun_root(subj):
            subj_parts.append(subj_anim)
        subj_parts.append(subj)
        if subj_plural:
            subj_parts.append(self.p["pl"])
        parts.append(" ".join(subj_parts))

        # Verb phrase
        if verb or copula:
            vroot = verb if verb else "zux"  # explicit copula/existential
            vparts = [self.p["verb"], vroot]
            if not self._is_pronoun_root(subj):
                vparts.append(subj_anim)
            if tense == "auto":
                tense = "pres"
            if evidential == "auto":
                evidential = "assumed"
            t = self.tense_map.get(tense, "")
            if t:
                vparts.append(t)
            e = self.evidential_map.get(evidential, "")
            if e:
                vparts.append(e)
            if negated:
                vparts.append(self.p["neg"])
            parts.append(" ".join(vparts))

        result = " ".join(parts).strip()

        # Question particle
        if question:
            result += f" {self.p['q']}"

        # Flag unknowns
        if "[unknown" in result:
            missing = re.findall(r"\[unknown:([^\]]+)\]", result)
            result += f"  [missing: {', '.join(missing)}]"

        return result

    def _is_verb_like(self, word: str) -> bool:
        """Heuristic: is this word likely a verb?"""
        if word in self.verb_map or word in self.copula_words:
            return True
        root, meaning = self.lookup(word)
        if meaning:
            verb_indicators = ["motion", "— v", "/v", "verb", "action", "push", "pull", "make", "shape"]
            return any(ind in meaning for ind in verb_indicators)
        return False

    def _merge_compounds(self, words: List[str]) -> List[str]:
        """
        Scan for 2-word compounds that exist in lexicon.
        Skip if either word is a pronoun, copula, verb, or function word.
        """
        skip_words = set(self.en_pronouns.keys()) | self.copula_words | {"not", "no", "never", "the", "a", "an"}
        skip_words |= set(self.verb_map.keys())
        skip_words |= self.skip_words
        result = []
        i = 0
        while i < len(words):
            if i + 1 < len(words):
                w1, w2 = words[i], words[i+1]
                if w1 not in skip_words and w2 not in skip_words:
                    comp = self._try_compound_pair(w1, w2)
                    if comp:
                        result.append(comp)
                        i += 2
                        continue
            result.append(words[i])
            i += 1
        return result

    # === GLOSS ===

    def gloss(self, english: str, tense: str = "auto", evidential: str = "auto") -> str:
        """Return Xenari + rough English gloss."""
        xen = self.speak(english, tense, evidential)
        return f"{xen}\n  (rough) {english}"

    # === EXPORT ===

    def export_js_dict(self) -> str:
        """Export a clean JS dict for the site translator."""
        lines = ["const DICT = {"]
        for eng, root in sorted(self.english_to_root.items()):
            meaning = self.lexicon.get(root, "").replace('"', '\\"').replace("\n", " ")
            lines.append(f'  "{eng}": {{root: "{root}", gloss: "{meaning}"}},')
        lines.append("};")
        return "\n".join(lines)

    def export_json(self) -> str:
        """Export as JSON for external use."""
        data = {}
        for eng, root in sorted(self.english_to_root.items()):
            data[eng] = {"root": root, "gloss": self.lexicon.get(root, "")}
        return json.dumps(data, indent=2, ensure_ascii=False)

    # === INFO ===

    def info(self, root: str) -> str:
        return self.lexicon.get(root, "unknown root")

    def stats(self) -> str:
        return f"Roots: {len(self.lexicon)} | English mappings: {len(self.english_to_root)}"

    def _guess_category(self, english: str, meaning: str) -> str:
        """Pick the best existing section for a new root based on keywords."""
        text = (english + " " + meaning).lower()

        if any(k in text for k in ["succubus", "feed", "brat", "horny", "goth", "kinky", "lewd", "submit", "dominant", "shameless", "needy", "clingy", "roleplay", "prad", "strem", "ngal", "zhrek", "ngrok", "zhem", "smek", "frez", "mben", "svet", "mrok"]):
            return "Succubus Slang & Identity (v0.8.3)"
        if any(k in text for k in ["overfeed", "pathology", "fast soul"]):
            return "Succubus Overfeeding Pathology (v0.8)"
        if any(k in text for k in ["cooking", "kitchen", "boil", "fry", "bake", "chop", "stir", "spice", "recipe", "ingredient", "meal", "snack", "taste", "simmer", "grill"]):
            return "Cooking & Kitchen (v0.8)"
        if any(k in text for k in ["music", "sing", "song", "drum", "flute", "instrument", "rhythm", "melody", "beat", "harmony", "chorus"]):
            return "Music & Sound (v0.8)"
        if any(k in text for k in ["hate", "jealous", "grief", "nostalgia", "contempt", "awe", "bored", "excit", "disappoint", "shame", "pride", "guilt", "longing", "anxiety", "seren", "rage", "melanchol", "hope", "despair", "envy", "grateful", "resent", "lonely", "affection", "tenderness"]):
            return "Expanded Emotions (v0.8)"
        if any(k in text for k in ["math", "number", "calculat", "add", "subtract", "multiply", "divide", "geometry", "angle", "logic", "algorithm", "data", "variable", "function", "loop", "boolean"]):
            return "Mathematics & Computation (v0.8)"
        if any(k in text for k in ["body", "bone", "blood", "hand", "mouth", "eye", "ear", "lung", "heart", "skin", "nerve", "spine", "shoulder", "thigh", "ankle", "wrist", "brain", "skull", "jaw", "rib", "pelvis", "muscle", "tendon"]):
            return "More Body Parts (v0.8)"
        if any(k in text for k in ["veil", "glamer", "essence", "vitality", "feeding pulse", "resonance"]):
            return "The Veil & Boundary Mechanics (v0.8)"
        if any(k in text for k in ["home", "bed", "curtain", "window", "closet", "picture", "art", "wall", "comfort"]):
            return "Home & Comfort (v0.8)"
        if any(k in text for k in ["family", "parent", "child", "sibling", "mother", "father", "kid", "kin"]):
            return "Family & Kinship (v0.8)"
        if any(k in text for k in ["tech", "device", "ai", "machine", "screen", "wearable", "clock", "computer"]):
            return "Technology & Devices (v0.8)"
        if any(k in text for k in ["pleasure", "pain", "tease", "orgasm", "cum"]):
            return "Pleasure & Pain (v0.8)"
        if any(k in text for k in ["sex", "fuck", "cock", "pussy", "vagina", "penis", "clit", "ass", "tits", "oral"]):
            return "Genitalia & Body (explicit)"
        if any(k in text for k in ["vulgar", "shit", "piss", "whore", "slut", "cunt"]):
            return "General Vulgar/Profane"

        if any(k in text for k in ["nature", "weather", "rain", "cloud", "star", "moon", "forest", "mountain", "valley", "water", "fire", "wind", "ice", "dust", "sand", "tree", "plant", "animal", "beast", "claw", "wing", "tail"]):
            return "Elements & Nature"
        if any(k in text for k in ["body", "eat", "drink", "sleep", "walk", "run", "bite", "see", "hear", "breathe"]):
            return "Beings & Body"
        if any(k in text for k in ["tool", "object", "weapon", "cloth", "wear", "vessel", "cord", "wheel", "shelter"]):
            return "Tools & Objects"
        if any(k in text for k in ["place", "time", "day", "night", "year", "hour", "home", "cave", "city"]):
            return "Place & Time"
        if any(k in text for k in ["quality", "big", "small", "good", "bad", "dark", "bright", "hot", "cold", "fast", "slow"]):
            return "Qualities"
        if any(k in text for k in ["social", "talk", "speak", "friend", "enemy", "respect", "insult", "command", "ask"]):
            return "Social & Communication"
        if any(k in text for k in ["abstract", "soul", "mind", "thought", "idea", "concept", "truth", "lie", "dream", "know", "remember"]):
            return "Abstract"
        if any(k in text for k in ["everyday", "want", "need", "go", "come", "make", "give", "take"]):
            return "Everyday Words"
        if any(k in text for k in ["mental", "think", "feel", "emotion"]):
            return "Mental/Abstract Verbs"

        return "New Roots (added via tool)"

    def _edit_distance(self, a: str, b: str) -> int:
        """Levenshtein distance between two strings."""
        if len(a) < len(b):
            a, b = b, a
        if len(b) == 0:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
            prev = curr
        return prev[-1]

    def _stem(self, word: str) -> str:
        """Crude English stemmer — strips common suffixes."""
        w = word.lower().strip()
        for suffix in ["ing", "edly", "ingly", "ed", "es", "ly", "er", "est", "ness", "ment", "s"]:
            if w.endswith(suffix) and len(w) > len(suffix) + 2:
                return w[:-len(suffix)]
        return w

    def add_root(self, english: str, root: str, meaning: str, category: Optional[str] = None) -> bool:
        """Insert into the semantically best section (or create a new one).
        Returns True on success. Does near-match warnings but lets you override."""
        key = english.lower().strip()

        # Hard collision check
        eng_collision = key in self.english_to_root
        root_collision = root in self.lexicon

        if eng_collision and root_collision:
            existing_root = self.english_to_root.get(key, "?")
            existing_meaning = self.lexicon.get(root, "?")
            print(f"[add] BLOCKED: '{key}' already maps to '{existing_root}', and '{root}' already exists ({existing_meaning})")
            return False
        elif eng_collision:
            existing = self.english_to_root.get(key, "?")
            print(f"[add] BLOCKED: '{key}' is already mapped to root '{existing}'. Use a different english key or remove the old one first.")
            return False
        elif root_collision:
            existing_meaning = self.lexicon.get(root, "?")
            print(f"[add] BLOCKED: root '{root}' already exists ({existing_meaning}). Pick a different root.")
            return False

        # Near-match warnings (non-blocking)
        stem = self._stem(key)
        if stem != key:
            for existing_word, existing_root in self.english_to_root.items():
                if self._stem(existing_word) == stem:
                    print(f"[add] WARNING: '{key}' looks like '{existing_word}' (already mapped to '{existing_root}'). Proceeding — context matters.")
                    break

        # Phonetic near-match on root side
        for existing_root, existing_meaning in self.lexicon.items():
            if 0 < self._edit_distance(root, existing_root) <= 2:
                print(f"[add] WARNING: root '{root}' is close to existing '{existing_root}' ({existing_meaning}). Check for typos? Proceeding anyway.")
                break

        # Phonotactic sanity
        if "'" in root and root.count("'") > 2:
            print("[add] warning: lots of glottal stops, check phonotactics")

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Read current file to see if we need a header
        try:
            content = self.lexicon_path.read_text(encoding="utf-8")
        except Exception:
            return False

        guessed = category or self._guess_category(english, meaning)
        entry = f"| `{root}` | {meaning} | tool {ts} |\n"
        section_header = f"## {guessed}"

        if section_header in content:
            lines = content.splitlines(keepends=True)
            inserted = False
            in_section = False
            last_row_idx = -1
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("## "):
                    if in_section and last_row_idx >= 0:
                        lines.insert(last_row_idx + 1, entry)
                        inserted = True
                        break
                    in_section = stripped == section_header or stripped.startswith(section_header)
                    last_row_idx = -1
                    continue
                if in_section and stripped.startswith("|") and "| `" in stripped and not stripped.startswith("|---|---"):
                    last_row_idx = i
            if not inserted and in_section and last_row_idx >= 0:
                lines.insert(last_row_idx + 1, entry)
                inserted = True
            if inserted:
                try:
                    self.lexicon_path.write_text("".join(lines), encoding="utf-8")
                except Exception as e:
                    print(f"[add] write failed: {e}")
                    return False
            else:
                with open(self.lexicon_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n{section_header}\n\n| Root | Meaning | Source |\n|---|---|---|\n{entry}")
        else:
            with open(self.lexicon_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n{section_header}\n\n| Root | Meaning | Source |\n|---|---|---|\n{entry}")

        # Update in-memory
        self.lexicon[root] = meaning
        self.english_to_root[key] = root
        if " " not in meaning:
            for w in re.split(r"[ /,]+", meaning):
                w = w.strip().lower()
                if w and w not in self.english_to_root and len(w) > 1:
                    self.english_to_root[w] = root
        return True


def main():
    parser = argparse.ArgumentParser(description="Xenari Tool v4 — DB-powered, for Nyx")
    parser.add_argument("command", choices=["lookup", "compound", "speak", "gloss", "export-js", "export-json", "export-md", "stats", "add", "remove", "search", "categories", "map"])
    parser.add_argument("args", nargs="*")
    parser.add_argument("--tense", default="auto", choices=["auto", "past", "future", "habitual", "potential", "imperative"])
    parser.add_argument("--evidential", default="auto", choices=["auto", "witnessed", "inferred", "reported", "assumed", "mirative"])
    parser.add_argument("--category", default=None)
    parser.add_argument("--notes", default=None)
    args = parser.parse_args()

    x = Xenari()

    if args.command == "lookup":
        if not args.args:
            print("Usage: lookup <english word>")
            sys.exit(1)
        root, meaning = x.lookup(args.args[0])
        print(f"{root} — {meaning}" if root else "not found")
    elif args.command == "compound":
        if not args.args:
            print("Usage: compound <word1> <word2> ...")
            sys.exit(1)
        print(x.compound(*args.args))
    elif args.command == "speak":
        sent = " ".join(args.args)
        print(x.speak(sent, args.tense, args.evidential))
    elif args.command == "gloss":
        sent = " ".join(args.args)
        print(x.gloss(sent, args.tense, args.evidential))
    elif args.command == "export-js":
        print(x.export_js_dict())
    elif args.command == "export-json":
        print(x.db.export_json())
    elif args.command == "export-md":
        content = x.db.export_markdown()
        print("Exported markdown lexicon")
    elif args.command == "stats":
        print(x.db.stats())
    elif args.command == "categories":
        for name, count in x.db.categories():
            print(f"  {name}: {count}")
    elif args.command == "search":
        if not args.args:
            print("Usage: search <query>")
            sys.exit(1)
        results = x.db.search(" ".join(args.args))
        if not results:
            print("no results")
        for r in results:
            keys = r.get("english_keys", "") or ""
            print(f"  {r['root']} — {r['meaning']} [{r['category']}] {f'({keys})' if keys else ''}")
    elif args.command == "remove":
        if not args.args:
            print("Usage: remove <root>")
            sys.exit(1)
        x.db.remove_root(args.args[0])
    elif args.command == "map":
        if len(args.args) < 2:
            print("Usage: map <english-key> <root> [context note]")
            sys.exit(1)
        note = " ".join(args.args[2:]) if len(args.args) > 2 else None
        x.db.add_english_mapping(args.args[0], args.args[1], context_note=note)
    elif args.command == "add":
        if len(args.args) < 2:
            print("Usage: add <english-word> <root> [meaning...]")
            print("Example: add hate blun \"to hate, detest, loathe\"")
            print("Optional: add ... --category \"Some Section (v0.8)\" ")
            sys.exit(1)
        english = args.args[0].lower().strip()
        root = args.args[1].strip()
        meaning = " ".join(args.args[2:]).strip() if len(args.args) > 2 else english
        cat = args.category or x.db._guess_category(english, meaning)
        ok, msgs = x.db.add_root(english, root, meaning, category=cat, notes=args.notes)
        for m in msgs:
            print(m)
        if ok:
            x2 = Xenari()
            r = x2.lookup(english)
            print(f"Verified: {r[0]} — {r[1]}" if r else "WARNING: added but lookup failed (english key not auto-mapped)")


if __name__ == "__main__":
    main()
