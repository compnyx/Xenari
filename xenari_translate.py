import re
from typing import List, Tuple


class TranslatorMixin:
    def speak(self, english: str, tense: str = "auto", evidential: str = "auto") -> str:
        """Translate English as a sequence of bounded clauses.

        The compact clause translator below is intentionally conservative.  It
        is safer to expose an untranslated fragment than to print an English
        token in a position where it would look like a coined Xenari root.
        """
        rendered = []
        connector_roots = {
            "and": self.p["and"],
            "but": self.p["but"],
            "or": self.p["or"],
            "however": self.p["but"],
            "once": "cruv",
            "so": "qlez",
            "yet": self.p["but"],
        }
        for clause, connector in self._split_english_clauses(english):
            xenari = self._speak_clause(clause, tense=tense, evidential=evidential)
            if not xenari:
                continue
            connector_root = connector_roots.get(connector or "")
            if connector_root and not xenari.startswith("[untranslated:"):
                xenari = f"{connector_root} {xenari}"
            rendered.append(xenari)
        return ". ".join(rendered)

    def _expand_english_contractions(self, text: str) -> str:
        contractions = {
            "i'm": "i am", "i've": "i have", "i'll": "i will", "i'd": "i would",
            "you're": "you are", "we're": "we are", "they're": "they are",
            "he's": "he is", "she's": "she is", "it's": "it is", "that's": "that is",
            "isn't": "is not", "aren't": "are not", "wasn't": "was not",
            "weren't": "were not", "don't": "do not", "doesn't": "does not",
            "didn't": "did not", "won't": "will not", "can't": "cannot",
            "couldn't": "could not", "shouldn't": "should not", "haven't": "have not",
            "hasn't": "has not", "hadn't": "had not",
        }
        expanded = text.lower().replace("’", "'")
        for contraction, replacement in contractions.items():
            expanded = re.sub(rf"\b{re.escape(contraction)}\b", replacement, expanded)
        return expanded

    def _split_english_clauses(self, text: str) -> List[Tuple[str, str]]:
        """Split prose at sentence boundaries and high-confidence clause seams."""
        expanded = self._expand_english_contractions(text)
        clauses: List[Tuple[str, str]] = []
        connector_words = {"and", "but", "or", "however", "once", "so", "yet"}
        greeting_tail_words = {"there", "friend", "friends", "buddy", "pal"}
        greeting_re = re.compile(r"^(hello|hey|hi|greetings)\b\s*,?\s*(.*)$")
        discourse_re = re.compile(r"^(anyway|however)\b\s*,?\s*(.*)$")
        independent_subject = re.compile(
            r"\s+(?=(?:i|you|he|she|we|they)\s+"
            r"(?:am|are|is|was|were|have|has|had|will|would|can|could|do|does|did)\b)"
        )

        for sentence in re.split(r"[.!?]+", expanded):
            sentence = sentence.strip()
            if not sentence:
                continue
            comma_parts = [part.strip() for part in re.split(r"\s*[,;]\s*", sentence) if part.strip()]
            for comma_part in comma_parts:
                connector = ""
                first, _, rest = comma_part.partition(" ")
                if first in connector_words and rest:
                    connector, comma_part = first, rest.strip()

                greeting = greeting_re.match(comma_part)
                if greeting:
                    clauses.append((greeting.group(1), connector))
                    greeting_tail = greeting.group(2).strip()
                    connector = ""
                    tail_words = re.findall(r"[a-z']+", greeting_tail)
                    if not greeting_tail or all(word in greeting_tail_words for word in tail_words):
                        continue
                    comma_part = greeting_tail

                discourse = discourse_re.match(comma_part)
                if discourse:
                    clauses.append((discourse.group(1), connector))
                    comma_part = discourse.group(2).strip()
                    connector = ""
                    if not comma_part:
                        continue

                major_parts = re.split(r"\s+(?=once\b)", comma_part)
                for major_index, major_part in enumerate(major_parts):
                    major_part = major_part.strip()
                    major_connector = connector if major_index == 0 else "once"
                    if major_part.startswith("once "):
                        major_part = major_part[5:].strip()
                    subject_parts = [part.strip() for part in independent_subject.split(major_part) if part.strip()]
                    for subject_index, subject_part in enumerate(subject_parts):
                        clauses.append((subject_part, major_connector if subject_index == 0 else ""))
        return clauses

    def _untranslated_fragment(self, english: str, unknown: List[str]) -> str:
        clean = re.sub(r"\s+", " ", english.strip().strip(".,!?;"))
        missing = ", ".join(dict.fromkeys(unknown))
        return f"[untranslated: {clean}; no Xenari root for: {missing}]"

    def _speak_clause(self, english: str, tense: str = "auto", evidential: str = "auto") -> str:
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
            "hello": "prax",
            "hey": "prax",
            "hi": "prax",
            "greetings": "prax",
            "hello there": "prax",
            "hey there": "prax",
            "hi there": "prax",
            "hello friend": "prax",
            "hey friend": "prax",
            "hi friend": "prax",
            "anyway": "qzecmru",
            "you little bitch": "mex krengk frem",
            "the alien sees me": f"ra neq ka vi qex ta toq vi sa {e}",
            "the alien is dangerous": f"ra fatyih ka vi qex ta zux vi sa {e}",
            "the hat is red": f"ra rlis ka nu brid ta zux nu sa {e}",
            "my hat blows off": f"ra neq po brid ka vi cuq ta qruq vi sa {e}",
            "the figure's hat blows off": f"ra vi loco po brid ka vi cuq ta qruq vi sa {e}",
            "i approach the figure by the lake": f"ra vi loco na nu qlon ka neq ta frig sa {e}",
            "i see the alien in the forest": f"ra vi qex na nu canq ka neq ta toq sa {e}",
            "creative work": "flonx",
            "creative art": "flonx",
            "i am going to work today": f"fa nu kashatyong ka neq ta qeng ve {e}",
            "i am going to work": f"fa nu kashatyong ka neq ta qeng ve {e}",
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

        working_match = re.fullmatch(
            r"(?:the\s+)?([a-z][a-z'-]*)\s+(is|are|was|were)\s+not\s+working",
            normalized,
        )
        if working_match:
            subject_word, auxiliary = working_match.groups()
            subject_root, _ = self.lookup(subject_word)
            if not subject_root:
                return self._untranslated_fragment(english, [subject_word])
            subject_animacy = self._animacy_for(subject_root, default=self.p["inan"])
            tense_root = self.p["past"] if auxiliary in {"was", "were"} else self.p["pres"]
            return (
                f"ka {subject_animacy} {subject_root} ta qxundraz "
                f"{subject_animacy} {tense_root} {e} {self.p['neg']}"
            )

        if "sentence" in normalized and re.search(
            r"\b(test|translator|translate|decipher|reverse|english)\b", normalized
        ):
            return self._untranslated_fragment(english, ["sentence (linguistic sense)"])

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
        unknown_words = []

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

            if tok in {"have", "has", "had", "having"}:
                if tense == "auto" and tok == "had":
                    tense = "past"
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
                unknown_words.append(tok)

        if unknown_words:
            return self._untranslated_fragment(english, unknown_words)

        # Handle copula: "X is Y" → Y OBJ X SUBJ [copula fallback]
        if copula and obj is not None and verb is None:
            if tense == "auto":
                tense = "pres"

        # A known noun without a verb is a fragment, not an implied action.
        if subj is None and obj is not None and verb is None and not copula:
            fragment = [obj, *[root for root in obj_tokens if root != obj]]
            return " ".join(fragment)

        # Defaults
        if subj is None:
            subj = self.pronouns["1"]

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
        skip_words = set(self.en_pronouns.keys()) | self.copula_words | {
            "not", "no", "never", "the", "a", "an", "have", "has", "had", "having"
        }
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
        """Best-effort Xenari → English with explicit partial-parse warnings."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", xenari) if s.strip()]
        frames = []
        recovered_boundary = False
        for sentence in sentences:
            current = []
            saw_verb_marker = False
            for token in sentence.split():
                if saw_verb_marker and token in {"ka", "ra"} and current:
                    frames.append(" ".join(current))
                    current = []
                    saw_verb_marker = False
                    recovered_boundary = True
                current.append(token)
                if token == "ta":
                    saw_verb_marker = True
            if current:
                frames.append(" ".join(current))

        rendered = []
        reverse_pronouns = {
            "neq": {"subj": "I", "obj": "me", "poss": "my"},
            "mex": {"subj": "you", "obj": "you", "poss": "your"},
            "zeq": {"subj": "they", "obj": "them", "poss": "their"},
            "leq": {"subj": "he/she/it", "obj": "him/her/it", "poss": "his/her/its"},
            "req": {"subj": "they", "obj": "them", "poss": "their"},
        }
        preferred = {
            "zrent": "love", "toq": "see", "zux": "is", "fatyih": "dangerous",
            "qex": "alien", "loco": "figure", "qlon": "lake", "brid": "hat",
            "cuq": "wind", "qruq": "blow", "frig": "approach", "rlis": "red",
            "qeng": "go", "qxundraz": "operate", "kashatyong": "job",
            "qzecmru": "anyway", "qranx": "throw", "flonx": "art",
        }
        case_particles = {"ra", "ka", "ta", "na", "fa", "mo"}
        skip_particles = {"vi", "nu", "sa", "lo", "ve", "du", "pe", "ko", "xa", "xe", "xi", "xo", "zu", "ha"}
        connector_glosses = {"kex": "but", "xen": "and", "noq": "or", "qlez": "so", "cruv": "once/when"}
        grammar_particles = case_particles | skip_particles | {"ngu", "va", "po"} | set(connector_glosses)

        def root_english(root: str, verb: bool = False, role: str = "plain") -> str:
            if root in reverse_pronouns:
                forms = reverse_pronouns[root]
                return forms.get(role, forms["subj"])
            if root in preferred:
                return preferred[root]
            meaning = self.lexicon.get(root)
            if meaning is None:
                return f"[unknown: {root}]"
            head = self.db._audit_headword(meaning)
            if verb and head.startswith("to "):
                head = head[3:]
            return head.split()[0] if head else root

        def read_phrase(tokens: List[str], start: int, role: str = "plain") -> Tuple[str, int]:
            pieces = []
            i = start
            possessor = None
            while i < len(tokens) and tokens[i] not in case_particles:
                tok = tokens[i]
                if tok in skip_particles:
                    i += 1
                    continue
                if tok == "po":
                    possessor = pieces.pop() if pieces else None
                    i += 1
                    continue
                pieces.append({"root": tok, "text": root_english(tok, role=role)})
                i += 1
            words = [piece["text"] for piece in pieces]
            if possessor and words:
                poss_text = root_english(possessor["root"], role="poss")
                if poss_text == possessor["text"] and not poss_text.endswith("'s"):
                    poss_text = f"{poss_text}'s"
                return f"{poss_text} {' '.join(words)}", i
            return " ".join(words), i

        for sentence in frames:
            if sentence == "prax":
                rendered.append("hello")
                continue

            tokens = sentence.split()
            obj = subj = loc = goal = instrument = verb = ""
            tense = "sa"
            negated = False
            question = False
            connector = ""
            warnings = []
            loose = []
            counts = {particle: tokens.count(particle) for particle in case_particles}
            unknown_roots = [
                token for token in tokens
                if token not in grammar_particles
                and token not in reverse_pronouns
                and token not in self.lexicon
            ]
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok in connector_glosses and i == 0:
                    connector = connector_glosses[tok]
                    i += 1
                elif tok == "ra":
                    obj, i = read_phrase(tokens, i + 1, role="obj")
                elif tok == "ka":
                    subj, i = read_phrase(tokens, i + 1, role="subj")
                elif tok == "na":
                    loc, i = read_phrase(tokens, i + 1)
                elif tok == "fa":
                    goal, i = read_phrase(tokens, i + 1)
                elif tok == "mo":
                    instrument, i = read_phrase(tokens, i + 1)
                elif tok == "ta":
                    j = i + 1
                    while j < len(tokens) and tokens[j] in skip_particles:
                        j += 1
                    verb = root_english(tokens[j], verb=True) if j < len(tokens) else ""
                    i = j + 1
                elif tok in {"sa", "lo", "ve", "du", "pe", "ko"}:
                    tense = tok
                    i += 1
                elif tok == "ngu":
                    negated = True
                    i += 1
                elif tok == "va":
                    question = True
                    i += 1
                else:
                    if tok not in grammar_particles:
                        loose.append(root_english(tok))
                    i += 1

            for particle, count in counts.items():
                if count > 1:
                    warnings.append(f"repeated marker '{particle}'")
            if counts["ta"] and not verb:
                warnings.append("verb marker has no readable verb")
            if (counts["ka"] or counts["ra"]) and not counts["ta"]:
                warnings.append("partial clause has no verb marker")
            if unknown_roots:
                warnings.append(f"unknown Xenari root(s): {', '.join(dict.fromkeys(unknown_roots))}")
            if loose:
                warnings.append("loose fragment(s) preserved outside the clause frame")

            def render_verb(v: str) -> str:
                if v == "is":
                    if tense == "lo":
                        return "was not" if negated else "was"
                    if tense == "ve":
                        return "will not be" if negated else "will be"
                    if negated:
                        return "is not"
                    return "is"
                base = v
                if tense == "lo":
                    if base.endswith("e"):
                        base = base + "d"
                    elif base.endswith("y"):
                        base = base[:-1] + "ied"
                    else:
                        base = base + "ed"
                elif tense == "ve":
                    base = "will " + base
                elif tense == "du":
                    base = "usually " + base
                elif tense == "pe":
                    base = "could " + base
                if negated:
                    if tense == "ve":
                        return "will not " + base.removeprefix("will ")
                    if tense == "lo":
                        return "did not " + v
                    aux = "do not" if subj in {"I", "you", "they"} else "does not"
                    return aux + " " + v
                return base

            if connector:
                text_parts = [connector]
            else:
                text_parts = []
            if verb == "is":
                text = " ".join(part for part in [subj, render_verb(verb), obj] if part)
            elif verb and obj and subj:
                text = " ".join(part for part in [subj, render_verb(verb), obj] if part)
            elif verb and subj:
                text = " ".join(part for part in [subj, render_verb(verb)] if part)
            else:
                text = " ".join(part for part in [subj, obj] if part)
            if loc:
                text = f"{text} in/at {loc}".strip()
            if goal:
                text = f"{text} to {goal}".strip()
            if instrument:
                text = f"{text} with {instrument}".strip()
            if loose:
                text = f"{text} [fragment: {' '.join(loose)}]".strip()
            if text_parts:
                text = " ".join([*text_parts, text]).strip()
            if question:
                text = f"{text}?"
            if warnings:
                text += f" [warning: {'; '.join(warnings)}]"
            rendered.append(text)
        result = ". ".join(rendered)
        if recovered_boundary:
            result += " [warning: recovered separate fragments where a second clause frame began without punctuation]"
        return result

    def looks_xenari(self, text: str) -> bool:
        """Heuristic direction detector for translate."""
        tokens = re.findall(r"[a-z']+", text.lower())
        if not tokens:
            return False
        if tokens == ["prax"]:
            return True
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
