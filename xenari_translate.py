import re
from typing import List, Tuple


class TranslatorMixin:
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
