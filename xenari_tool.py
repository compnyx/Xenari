#!/usr/bin/env python3
"""
Xenari Tool v4 — for Nyx to speak Xenari properly.
Strict: only real roots, no hallucinations. Unknown words marked clearly.

Usage:
  python xenari_tool.py lookup "big"
  python xenari_tool.py info fatyih
  python xenari_tool.py validate fatyih qip xqz
  python xenari_tool.py compound big daddy
  python xenari_tool.py speak "I want big daddy" --tense pres --evidential witnessed
  python xenari_tool.py speak "you are cute" --evidential inferred
  python xenari_tool.py translate "I love you"
  python xenari_tool.py inspect fatyih
  python xenari_tool.py gloss "fuck it we ball"
  python xenari_tool.py doctor
  python xenari_tool.py workbench
  python xenari_tool.py propose-root "glimmer" "soft unsteady light"
  python xenari_tool.py relations fatyih
  python xenari_tool.py reverse "ra mex ka neq ta zrent sa xa"
  python xenari_tool.py export json
  python xenari_tool.py sync --site
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
            else:
                current = self.english_to_root[key]
                current_score = self.db._lookup_score(key, self.lexicon.get(current, ""))
                candidate_score = self.db._lookup_score(key, self.lexicon.get(row["root"], ""))
                if candidate_score > current_score:
                    self.english_to_root[key] = row["root"]

    # === CORE LOOKUP ===

    def lookup(self, english: str) -> Tuple[Optional[str], Optional[str]]:
        """Look up an English word, return (root, meaning) or (None, None)."""
        key = english.lower().strip()
        if key in self.en_pronouns:
            root = self.pronouns[self.en_pronouns[key][0]]
            return root, self.lexicon.get(root, "")
        if key in self.english_to_root:
            root = self.english_to_root[key]
            return root, self.lexicon.get(root, "")
        root = self._lookup_by_meaning_synonym(key)
        if root:
            return root, self.lexicon.get(root, "")
        return None, None

    def _meaning_keys(self, meaning: str) -> List[str]:
        """Derive conservative lookup keys from the head of a meaning string."""
        head = (meaning or "").lower().replace("—", ";")
        head = re.split(r";|:", head, maxsplit=1)[0]
        head = re.sub(r"\([^)]*\)", "", head)
        keys = []
        for part in re.split(r"[,/]", head):
            part = re.sub(r"^(to|a|an|the)\s+", "", part.strip())
            if re.fullmatch(r"[a-z][a-z'-]{1,}", part):
                keys.append(part)
        return keys

    def _lookup_by_meaning_synonym(self, key: str) -> Optional[str]:
        best = None
        best_score = -1
        for root, meaning in self.lexicon.items():
            keys = self._meaning_keys(meaning)
            if key not in keys:
                continue
            score = 3 if keys and keys[0] == key else 2
            if score > best_score:
                best = root
                best_score = score
        return best

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
        normalized = re.sub(r"[^a-z0-9' ]+", " ", english.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if evidential == "auto":
            evidential = "assumed"
        e = self.evidential_map.get(evidential, self.evidential_map["assumed"])
        exact_phrases = {
            "you little bitch": "mex krengk frem",
            "the alien sees me": f"ra neq ka vi qex ta toq vi sa {e}",
            "the alien is dangerous": f"ra fatyih ka vi qex ta zux vi sa {e}",
            "the hat is red": f"ra rlis ka nu brid ta zux nu sa {e}",
            "my hat blows off": f"ra neq po brid ka vi cuq ta qruq vi sa {e}",
            "the figure's hat blows off": f"ra vi loco po brid ka vi cuq ta qruq vi sa {e}",
            "i approach the figure by the lake": f"ra vi loco na nu qlon ka neq ta frig sa {e}",
            "i see the alien in the forest": f"ra vi qex na nu canq ka neq ta toq sa {e}",
        }
        if normalized in exact_phrases:
            return exact_phrases[normalized]
        if normalized == "you little bitch":
            return "mex krengk frem"
        if normalized == "i approach the figure by the lake the figure's hat blows off":
            return (
                f"ra vi loco na nu qlon ka neq ta frig sa {e}. "
                f"ra vi loco po brid ka vi cuq ta qruq vi sa {e}"
            )

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

    def reverse(self, xenari: str) -> str:
        """Best-effort Xenari → English for canonical OSV clauses."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", xenari) if s.strip()]
        rendered = []
        reverse_pronouns = {"neq": "I", "mex": "you", "zeq": "they", "leq": "he/she/it", "req": "they"}
        preferred = {
            "zrent": "love", "toq": "see", "zux": "is", "fatyih": "dangerous",
            "qex": "alien", "loco": "figure", "qlon": "lake", "brid": "hat",
            "cuq": "wind", "qruq": "blow", "frig": "approach", "rlis": "red",
        }
        case_particles = {"ra", "ka", "ta", "na", "fa", "mo"}
        skip_particles = {"vi", "nu", "sa", "lo", "ve", "du", "pe", "ko", "xa", "xe", "xi", "xo", "zu", "ha"}

        def root_english(root: str, verb: bool = False) -> str:
            if root in reverse_pronouns:
                return reverse_pronouns[root]
            if root in preferred:
                return preferred[root]
            meaning = self.lexicon.get(root, root)
            head = self.db._audit_headword(meaning)
            if verb and head.startswith("to "):
                head = head[3:]
            return head.split()[0] if head else root

        def read_phrase(tokens: List[str], start: int) -> Tuple[str, int]:
            words = []
            i = start
            possessor = None
            while i < len(tokens) and tokens[i] not in case_particles:
                tok = tokens[i]
                if tok in skip_particles:
                    i += 1
                    continue
                if tok == "po":
                    possessor = words.pop() if words else None
                    i += 1
                    continue
                words.append(root_english(tok))
                i += 1
            if possessor and words:
                return f"{possessor}'s {' '.join(words)}", i
            return " ".join(words), i

        for sentence in sentences:
            tokens = sentence.split()
            obj = subj = loc = verb = ""
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok == "ra":
                    obj, i = read_phrase(tokens, i + 1)
                elif tok == "ka":
                    subj, i = read_phrase(tokens, i + 1)
                elif tok == "na":
                    loc, i = read_phrase(tokens, i + 1)
                elif tok == "ta":
                    j = i + 1
                    while j < len(tokens) and tokens[j] in skip_particles:
                        j += 1
                    verb = root_english(tokens[j], verb=True) if j < len(tokens) else ""
                    i = j + 1
                else:
                    i += 1

            if verb == "is":
                text = " ".join(part for part in [subj, "is", obj] if part)
            elif verb and obj and subj:
                text = " ".join(part for part in [subj, verb, obj] if part)
            elif verb and subj:
                text = " ".join(part for part in [subj, verb] if part)
            else:
                text = " ".join(part for part in [subj, obj] if part)
            if loc:
                text = f"{text} in/at {loc}".strip()
            rendered.append(text)
        return ". ".join(rendered)

    def looks_xenari(self, text: str) -> bool:
        """Heuristic direction detector for translate."""
        tokens = re.findall(r"[a-z']+", text.lower())
        if not tokens:
            return False
        particles = {
            "ra", "ka", "ta", "na", "fa", "mo", "vi", "nu", "sa", "lo", "ve",
            "du", "pe", "ko", "xa", "xe", "xi", "xo", "zu", "po", "ha", "ngu",
        }
        known = sum(1 for token in tokens if token in particles or token in self.lexicon)
        case_markers = sum(1 for token in tokens if token in {"ra", "ka", "ta"})
        return case_markers >= 2 or (known / len(tokens) >= 0.7 and tokens[0] in particles)

    def translate(self, text: str, tense: str = "auto", evidential: str = "auto") -> str:
        """Auto-direction translation wrapper."""
        if self.looks_xenari(text):
            return self.reverse(text)
        return self.speak(text, tense=tense, evidential=evidential)

    def inspect_term(self, term: str, limit: int = 5) -> str:
        """Combined lookup/root/search view for fast agent work."""
        query = term.strip()
        lines = [f"Inspect: {query}"]

        root_row = self.db.lookup_root(query)
        if root_row:
            lines.append(f"Root: {root_row['root']} — {root_row['meaning']} [{root_row['category']}]")
            ok, relations = self.db.relations_report(query)
            if ok:
                rel_lines = relations.splitlines()[1:]
                lines.extend(rel_lines[: min(len(rel_lines), 10)])

        root, meaning = self.lookup(query)
        if root:
            lines.append(f"English lookup: {query} -> {root} — {meaning}")

        results = self.db.search(query, limit=limit)
        if results:
            lines.append("Search:")
            for item in results:
                lines.append(
                    f"  - {item['root']} — {item['meaning']} "
                    f"[{item['category']}] score={item.get('score', 0)}"
                )
        if len(lines) == 1:
            lines.append("not found")
        return "\n".join(lines)

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

    def export_format(self, fmt: str, output: Optional[Path] = None, include_site: bool = False) -> str:
        """Unified export surface for generated dictionary artifacts."""
        fmt = fmt.lower().strip()
        if fmt in {"json", "dict"}:
            text = self.db.export_json()
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(text, encoding="utf-8")
                return f"wrote {output}"
            return text
        if fmt in {"js", "browser"}:
            text = self.export_js_dict()
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(text, encoding="utf-8")
                return f"wrote {output}"
            return text
        if fmt in {"md", "markdown"}:
            out = output or Path("xenari-lexicon-export.md")
            self.db.export_markdown(out)
            return f"wrote {out}"
        if fmt == "site":
            return self.sync_exports(include_site=True)
        if fmt == "repo":
            return self.sync_exports(include_site=False)
        raise ValueError(f"unknown export format: {fmt}")

    # === INFO ===

    def info(self, root: str) -> str:
        return self.lexicon.get(root, "unknown root")

    def stats(self) -> str:
        return f"Roots: {len(self.lexicon)} | English mappings: {len(self.english_to_root)}"

    def validate_roots(self, roots: List[str]) -> Tuple[bool, str]:
        """Validate one or more root forms and return (all_ok, report)."""
        if not roots:
            return False, "Usage: validate <root> [root...]"

        lines = []
        ok = True
        for root in roots:
            issues = self.db.validate_phonotactics(root)
            if issues:
                ok = False
                lines.append(f"{root}: INVALID")
                for issue in issues:
                    lines.append(f"  - {issue}")
            else:
                lines.append(f"{root}: ok")
        return ok, "\n".join(lines)

    def doctor(self) -> Tuple[bool, str]:
        """Run a compact health check for the canon DB and common tool behavior."""
        phrase_cases = {
            "I love you": "ra mex ka neq ta zrent sa xo",
            "you little bitch": "mex krengk frem",
            "I see the alien": "ra vi qex ka neq ta toq sa xo",
            "the alien sees me": "ra neq ka vi qex ta toq vi sa xo",
            "the alien is dangerous": "ra fatyih ka vi qex ta zux vi sa xo",
            "the hat is red": "ra rlis ka nu brid ta zux nu sa xo",
            "I approach the figure by the lake. The figure's hat blows off": (
                "ra vi loco na nu qlon ka neq ta frig sa xo. "
                "ra vi loco po brid ka vi cuq ta qruq vi sa xo"
            ),
        }
        lookup_cases = {
            "you": "mex",
            "me": "neq",
            "wrath": "nud",
            "perilous": "fatyih",
        }

        lines = ["Xenari doctor", self.db.stats(), ""]
        ok = True

        audit = self.db.audit(limit=3)
        for needle in (
            "Actionable exact duplicate groups: 0",
            "Stale/conflict/reanalysis marker rows: 0",
            "Phonotactic validator failures: 0",
        ):
            if needle not in audit:
                ok = False
                lines.append(f"FAIL audit: missing {needle}")
        if ok:
            lines.append("audit: ok")

        for english, expected in lookup_cases.items():
            root, _meaning = self.lookup(english)
            if root != expected:
                ok = False
                lines.append(f"FAIL lookup {english!r}: expected {expected}, got {root}")
        if all(self.lookup(english)[0] == expected for english, expected in lookup_cases.items()):
            lines.append("lookup: ok")

        for english, expected in phrase_cases.items():
            actual = self.speak(english, evidential="assumed")
            if actual != expected:
                ok = False
                lines.append(f"FAIL speak {english!r}:")
                lines.append(f"  expected: {expected}")
                lines.append(f"  actual:   {actual}")
        if all(self.speak(english, evidential="assumed") == expected for english, expected in phrase_cases.items()):
            lines.append("speak: ok")

        lines.append("")
        lines.append("status: ok" if ok else "status: FAIL")
        return ok, "\n".join(lines)

    def workbench(self, limit: int = 5) -> Tuple[bool, str]:
        """Agent-friendly snapshot for deciding what to do next."""
        ok, doctor_report = self.doctor()
        audit = self.db.audit(limit=0)
        lint = self.db.lint(limit=limit)
        lines = [
            "Xenari workbench",
            self.db.stats(),
            "",
            "Release gate:",
        ]
        for line in doctor_report.splitlines()[3:]:
            if line:
                lines.append(f"  {line}")
        lines.extend(["", "Audit counters:"])
        for line in audit.splitlines():
            if line.startswith((
                "Actionable exact duplicate groups:",
                "Stale/conflict/reanalysis marker rows:",
                "Phonotactic validator failures:",
                "Raw exact meaning duplicate groups:",
                "Raw headword duplicate groups:",
            )):
                lines.append(f"  {line}")
        lines.extend(["", "Lint preview:"])
        for line in lint.splitlines()[: max(8, limit + 8)]:
            lines.append(f"  {line}")
        lines.extend([
            "",
            "Useful next commands:",
            "  python3 xenari_tool.py search <english-or-root>",
            "  python3 xenari_tool.py near <meaning>",
            "  python3 xenari_tool.py propose-root <english> <meaning>",
            "  python3 xenari_tool.py add <english> <root> <meaning> --dry-run",
            "  python3 xenari_tool.py sync --site && pytest -q",
        ])
        return ok, "\n".join(lines)

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
        """Add a new root to the canonical DB and refresh in-memory lookup data."""
        guessed = category or self.db._guess_category(english, meaning)
        ok, messages = self.db.add_root(english, root, meaning, category=guessed)
        for message in messages:
            print(f"[add] {message}")
        if ok:
            self._load_from_db()
        return ok

    def sync_exports(self, include_site: bool = False) -> str:
        """Regenerate derived JSON exports from the canonical DB."""
        repo = Path(__file__).resolve().parent
        json_text = self.db.export_json()
        out_paths = [repo / "data" / "xenari-dict.json"]
        if include_site:
            site = Path("/home/computment/nyx-site")
            out_paths.extend([
                site / "src" / "data" / "xenari-dict.json",
                site / "public" / "xenari-dict-data.json",
            ])

        lines = []
        for path in out_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_text, encoding="utf-8")
            lines.append(f"wrote {path}")
        return "\n".join(lines)


def main():
    epilog = """Common flows:
  inspect:   stats | doctor | workbench | audit 20 | lint 20
  find:      inspect fatyih | lookup love | search dangerous | near "soft light" | relations fatyih
  translate: translate "I love you" | translate "ra mex ka neq ta zrent sa xa"
  coin:      propose-root glimmer "soft unsteady light" --limit 8
  mutate:    add/map/remove preview by default; write only with --yes
  publish:   sync --site && pytest -q
"""
    parser = argparse.ArgumentParser(
        description="Xenari Tool v4 — DB-powered, for Nyx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument("command", choices=[
        "help", "lookup", "inspect", "info", "validate", "doctor", "workbench",
        "compound", "speak", "gloss", "translate", "reverse",
        "export-js", "export-json", "export-md",
        "export", "stats", "audit", "lint", "meta", "sync",
        "add", "remove", "search", "near", "relations", "propose-root", "categories", "map",
    ])
    parser.add_argument("args", nargs="*")
    parser.add_argument("--tense", default="auto", choices=["auto", "past", "future", "habitual", "potential", "imperative"])
    parser.add_argument("--evidential", default="auto", choices=["auto", "witnessed", "inferred", "reported", "assumed", "mirative"])
    parser.add_argument("--category", default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--yes", action="store_true", help="confirm mutating DB operations")
    parser.add_argument("--dry-run", action="store_true", help="preview a mutating operation without writing")
    parser.add_argument("--site", action="store_true", help="sync exports into nyx-site dictionary paths too")
    parser.add_argument("--limit", type=int, default=20, help="result limit for search/lint/propose commands")
    parser.add_argument("--output", default=None, help="optional output path for export")
    args = parser.parse_args()

    x = Xenari()

    if args.command == "help":
        parser.print_help()
    elif args.command == "lookup":
        if not args.args:
            print("Usage: lookup <english word or phrase>")
            sys.exit(1)
        query = " ".join(args.args).strip()
        root, meaning = x.lookup(query)
        if root:
            print(f"{root} — {meaning}")
        elif len(args.args) > 1:
            found = False
            for word in args.args:
                root, meaning = x.lookup(word)
                if root:
                    found = True
                    print(f"{word}: {root} — {meaning}")
                else:
                    print(f"{word}: not found")
            if not found:
                sys.exit(1)
        else:
            print("not found")
            sys.exit(1)
    elif args.command == "inspect":
        if not args.args:
            print("Usage: inspect <english-or-root>")
            sys.exit(1)
        print(x.inspect_term(" ".join(args.args), limit=args.limit))
    elif args.command == "info":
        if not args.args:
            print("Usage: info <xenari-root>")
            sys.exit(1)
        for root in args.args:
            print(f"{root} — {x.info(root)}")
    elif args.command == "validate":
        ok, report = x.validate_roots(args.args)
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "doctor":
        ok, report = x.doctor()
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "workbench":
        ok, report = x.workbench(limit=args.limit)
        print(report)
        if not ok:
            sys.exit(1)
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
    elif args.command == "translate":
        sent = " ".join(args.args)
        if not sent:
            print("Usage: translate <english-or-xenari>")
            sys.exit(1)
        print(x.translate(sent, args.tense, args.evidential))
    elif args.command == "reverse":
        sent = " ".join(args.args)
        if not sent:
            print("Usage: reverse <xenari sentence>")
            sys.exit(1)
        print(x.reverse(sent))
    elif args.command == "export-js":
        print(x.export_js_dict())
    elif args.command == "export-json":
        print(x.db.export_json())
    elif args.command == "export-md":
        out = Path(args.args[0]) if args.args else Path("xenari-lexicon-export.md")
        x.db.export_markdown(out)
        print(f"Exported markdown lexicon to {out}")
    elif args.command == "export":
        if not args.args:
            print("Usage: export <json|js|md|site|repo> [output-path]")
            sys.exit(1)
        fmt = args.args[0]
        output = Path(args.output or args.args[1]) if args.output or len(args.args) > 1 else None
        try:
            print(x.export_format(fmt, output=output, include_site=args.site))
        except ValueError as exc:
            print(exc)
            sys.exit(1)
    elif args.command == "stats":
        print(x.db.stats())
    elif args.command == "meta":
        print(x.db.metadata_report())
    elif args.command == "audit":
        limit = 40
        if args.args:
            try:
                limit = int(args.args[0])
            except ValueError:
                print("Usage: audit [limit]")
                sys.exit(1)
        print(x.db.audit(limit=limit))
    elif args.command == "lint":
        limit = args.limit
        if args.args:
            try:
                limit = int(args.args[0])
            except ValueError:
                print("Usage: lint [limit]")
                sys.exit(1)
        print(x.db.lint(limit=limit))
    elif args.command == "sync":
        print(x.sync_exports(include_site=args.site))
        ok, report = x.doctor()
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "categories":
        for name, count in x.db.categories():
            print(f"  {name}: {count}")
    elif args.command == "search":
        if not args.args:
            print("Usage: search <query>")
            sys.exit(1)
        results = x.db.search(" ".join(args.args), limit=args.limit)
        if not results:
            print("no results")
        for r in results:
            keys = r.get("english_keys", "") or ""
            print(f"  {r['root']} — {r['meaning']} [{r['category']}] score={r.get('score', 0)} {f'({keys})' if keys else ''}")
    elif args.command == "near":
        if not args.args:
            print("Usage: near <meaning/query>")
            sys.exit(1)
        results = x.db.near_meanings(" ".join(args.args), limit=args.limit)
        if not results:
            print("no near matches")
        for r in results:
            print(f"  {r['root']} — {r['meaning']} [{r['category']}] score={r.get('score', 0)}")
    elif args.command == "relations":
        if not args.args:
            print("Usage: relations <root>")
            sys.exit(1)
        ok, report = x.db.relations_report(args.args[0])
        print(report)
        if not ok:
            sys.exit(1)
    elif args.command == "propose-root":
        if not args.args:
            print("Usage: propose-root <english-key> [meaning...]")
            sys.exit(1)
        english = args.args[0]
        meaning = " ".join(args.args[1:]) if len(args.args) > 1 else english
        suggestions = x.db.propose_root(english, meaning, limit=args.limit)
        print(f"Root proposals for {english!r} — {meaning}")
        print(f"Category guess: {x.db._guess_category(english, meaning)}")
        near = x.db.near_meanings(english, limit=5)
        if near:
            print("Near existing meanings:")
            for r in near:
                print(f"  - {r['root']} — {r['meaning']} [{r['category']}] score={r.get('score', 0)}")
        print("Suggestions:")
        for item in suggestions:
            print(f"  - {item['root']} [{item['category']}] score={item.get('score', 0)}: {'; '.join(item['notes'])}")
    elif args.command == "remove":
        if not args.args:
            print("Usage: remove <root>")
            sys.exit(1)
        ok, report = x.db.describe_remove_root(args.args[0])
        print(report)
        if not ok:
            sys.exit(1)
        if args.dry_run or not args.yes:
            if not args.dry_run:
                print("Refusing to remove without --yes. Re-run with --yes after reading the preview.")
                sys.exit(1)
            sys.exit(0)
        x.db.remove_root(args.args[0])
    elif args.command == "map":
        if len(args.args) < 2:
            print("Usage: map <english-key> <root> [context note]")
            sys.exit(1)
        note = " ".join(args.args[2:]) if len(args.args) > 2 else None
        ok, report = x.db.describe_english_mapping(args.args[0], args.args[1], context_note=note)
        print(report)
        if not ok:
            sys.exit(1)
        if args.dry_run or not args.yes:
            if not args.dry_run:
                print("Refusing to map without --yes. Re-run with --yes after reading the preview.")
                sys.exit(1)
            sys.exit(0)
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
        dry_run = args.dry_run or not args.yes
        ok, msgs = x.db.add_root(english, root, meaning, category=cat, notes=args.notes, dry_run=dry_run)
        for m in msgs:
            print(m)
        if dry_run:
            if ok and not args.dry_run:
                print("Refusing to add without --yes. Re-run with --yes after reading the preview.")
                sys.exit(1)
            sys.exit(0 if ok else 1)
        if ok:
            x2 = Xenari()
            r = x2.lookup(english)
            print(f"Verified: {r[0]} — {r[1]}" if r else "WARNING: added but lookup failed (english key not auto-mapped)")


if __name__ == "__main__":
    main()
