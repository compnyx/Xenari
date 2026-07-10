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
            "you're": "you are", "you've": "you have", "you'll": "you will", "you'd": "you would",
            "we're": "we are", "we've": "we have", "we'll": "we will", "we'd": "we would",
            "they're": "they are", "they've": "they have", "they'll": "they will", "they'd": "they would",
            "he's": "he is", "she's": "she is", "it's": "it is", "that's": "that is",
            "he'll": "he will", "she'll": "she will", "he'd": "he would", "she'd": "she would",
            "what's": "what is",
            "isn't": "is not", "aren't": "are not", "wasn't": "was not",
            "weren't": "were not", "don't": "do not", "doesn't": "does not",
            "didn't": "did not", "won't": "will not", "can't": "can not",
            "cannot": "can not",
            "wouldn't": "would not", "couldn't": "could not", "shouldn't": "should not",
            "mustn't": "must not", "haven't": "have not",
            "hasn't": "has not", "hadn't": "had not",
            "let's": "let us", "y'all": "you all",
        }
        apostrophes = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "＇": "'", "`": "'"})
        expanded = text.lower().translate(apostrophes)
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
                    antecedent = None
                    if len(subject_parts) > 1:
                        antecedent_match = (
                            re.search(r"([a-z][a-z'-]*)$", subject_parts[0])
                            if re.search(r"\b(?:a|an|the)\b", subject_parts[0])
                            else None
                        )
                        antecedent = antecedent_match.group(1) if antecedent_match else None
                    for subject_index, subject_part in enumerate(subject_parts):
                        if subject_index and antecedent:
                            subject_part = re.sub(
                                r"^((?:i|you|he|she|we|they)\s+"
                                r"(?:am|are|is|was|were)\s+[a-z][a-z'-]*ing)\s+"
                                r"(?=(?:in|for)\b)",
                                rf"\1 the {antecedent} ",
                                subject_part,
                            )
                        clauses.append((subject_part, major_connector if subject_index == 0 else ""))
        return clauses

    def _untranslated_fragment(self, english: str, unknown: List[str]) -> str:
        clean = re.sub(r"\s+", " ", english.strip().strip(".,!?;"))
        missing = ", ".join(dict.fromkeys(unknown))
        return f"[untranslated: {clean}; no Xenari root for: {missing}]"

    def _unsupported_fragment(self, english: str, reason: str) -> str:
        """Keep unsupported grammar readable instead of dropping its meaning."""
        clean = re.sub(r"\s+", " ", english.strip().strip(".,!?;"))
        return f"[untranslated: {clean}; unsupported grammar: {reason}]"

    def _english_subject_root(self, word: str):
        info = self.en_pronouns.get(word)
        if info:
            return self.pronouns[info[0]]
        root, _ = self.lookup(word)
        return root

    def _known_verb_root(self, word: str):
        """Resolve a real verb root, including common English inflections."""
        clean = word.lower().strip()
        if clean in self.verb_map:
            return self.verb_map[clean]
        root, meaning = self.lookup(clean)
        if root and (meaning or "").lower().startswith("to "):
            return root
        irregular = {
            "acquired": "acquire", "obtained": "obtain", "sent": "send",
            "made": "make", "written": "write", "wrote": "write",
        }
        candidates = [irregular.get(clean, "")]
        if clean.endswith("ing") and len(clean) > 4:
            candidates.extend([clean[:-3], clean[:-3] + "e"])
        if clean.endswith("ied") and len(clean) > 4:
            candidates.append(clean[:-3] + "y")
        if clean.endswith("ed") and len(clean) > 3:
            candidates.extend([clean[:-2], clean[:-1]])
        if clean.endswith("es") and len(clean) > 3:
            candidates.extend([clean[:-2], clean[:-1]])
        elif clean.endswith("s") and len(clean) > 2:
            candidates.append(clean[:-1])
        for candidate in candidates:
            if not candidate:
                continue
            if candidate in self.verb_map:
                return self.verb_map[candidate]
            root, meaning = self.lookup(candidate)
            if root and (meaning or "").lower().startswith("to "):
                return root
        return None

    def _render_simple_frame(
        self,
        subject_root: str,
        verb_root: str,
        *,
        object_roots=None,
        location_root=None,
        tense_root="sa",
        evidence_root="xo",
        question=False,
        polite=False,
        purpose=None,
        goal_root=None,
        negated=False,
    ) -> str:
        """Render a small, fully-known clause without inventing any roots."""
        parts = []
        if object_roots:
            parts.extend(["ra", "nu", *object_roots])
        if location_root:
            parts.extend(["na", "nu", location_root])
        if goal_root:
            parts.extend(["fa", "nu", goal_root])
        parts.append("ka")
        subject_animacy = self._animacy_for(subject_root, default=self.p["inan"])
        if not self._is_pronoun_root(subject_root):
            parts.append(subject_animacy)
        parts.extend([subject_root, "ta", verb_root])
        if not self._is_pronoun_root(subject_root):
            parts.append(subject_animacy)
        parts.extend([tense_root, evidence_root])
        if polite:
            please_root, _ = self.lookup("please")
            if please_root:
                parts.append(please_root)
        if question:
            parts.append(self.p["q"])
        if purpose:
            purpose_subject, purpose_verb, purpose_object = purpose
            parts.append("frex")
            if purpose_object:
                parts.extend(["ra", "nu", *purpose_object])
            parts.append("ka")
            purpose_animacy = self._animacy_for(purpose_subject, default=self.p["anim"])
            if not self._is_pronoun_root(purpose_subject):
                parts.append(purpose_animacy)
            parts.extend([purpose_subject, "ta", purpose_verb])
            if not self._is_pronoun_root(purpose_subject):
                parts.append(purpose_animacy)
        if negated:
            parts.append(self.p["neg"])
        return " ".join(parts)

    def _speak_common_pattern(self, normalized: str, evidence_root: str):
        """Handle common English frames whose structure is unambiguous."""
        going_to_work = re.fullmatch(
            r"(i|you|he|she|we|they)\s+(?:am|are|is)\s+(not\s+)?"
            r"going\s+to\s+work(?:\s+(?:today|tomorrow))?",
            normalized,
        )
        if going_to_work:
            subject, negated = going_to_work.groups()
            subject_root = self._english_subject_root(subject)
            job_root, _ = self.lookup("job")
            if subject_root and job_root:
                return self._render_simple_frame(
                    subject_root,
                    self._known_verb_root("go"),
                    goal_root=job_root,
                    tense_root="ve",
                    evidence_root=evidence_root,
                    negated=bool(negated),
                )

        copula = re.fullmatch(
            r"(this|that)\s+(is|was)\s+(?:a\s+)?(?:(test)\s+)?(sentence|utterance)",
            normalized,
        )
        if copula:
            demonstrative, auxiliary, modifier, noun = copula.groups()
            subject_root, _ = self.lookup(demonstrative)
            noun_root, _ = self.lookup(noun)
            modifier_root, _ = self.lookup(modifier) if modifier else (None, None)
            if subject_root and noun_root and (not modifier or modifier_root):
                object_roots = [noun_root]
                if modifier_root:
                    object_roots.append(modifier_root)
                return self._render_simple_frame(
                    subject_root,
                    "zux",
                    object_roots=object_roots,
                    tense_root="lo" if auxiliary == "was" else "sa",
                    evidence_root=evidence_root,
                )

        perfect = re.fullmatch(
            r"(i|you|he|she|we|they)\s+(have|has|had)\s+"
            r"(got|gotten|acquired|obtained)\s+(?:the\s+|an?\s+)?"
            r"([a-z][a-z'-]*)(?:\s+of\s+([a-z][a-z'-]*))?",
            normalized,
        )
        if perfect:
            subject, _auxiliary, verb, obj, possessor = perfect.groups()
            subject_root = self._english_subject_root(subject)
            verb_root = self._known_verb_root(verb)
            object_root, _ = self.lookup(obj)
            possessor_root, _ = self.lookup(possessor) if possessor else (None, None)
            if subject_root and verb_root and object_root and (not possessor or possessor_root):
                object_roots = (
                    [possessor_root, self.p["poss"], object_root]
                    if possessor_root else [object_root]
                )
                return self._render_simple_frame(
                    subject_root,
                    verb_root,
                    object_roots=object_roots,
                    tense_root="lo",
                    evidence_root=evidence_root,
                )

        modal = re.fullmatch(
            r"(can|could|should|will|would)\s+(i|you|he|she|we|they)\s+"
            r"(reverse engineer|reverse-engineer|decipher|decode|translate)\s+"
            r"(?:this|that|the|an?)\s+(sentence|utterance)"
            r"(\s+back\s+to\s+english)?(\s+please)?",
            normalized,
        )
        if modal:
            modal_word, subject, verb, obj, language_target, please = modal.groups()
            subject_root = self._english_subject_root(subject)
            verb_root = self._known_verb_root(verb)
            object_root, _ = self.lookup(obj)
            if subject_root and verb_root and object_root:
                rendered = self._render_simple_frame(
                    subject_root,
                    verb_root,
                    object_roots=[object_root],
                    tense_root="ve" if modal_word in {"will", "would"} else "pe",
                    evidence_root=evidence_root,
                    question=True,
                    polite=bool(please),
                )
                if language_target:
                    rendered += " [partial: omitted language target: English]"
                return rendered

        action = re.fullmatch(
            r"(i|you|he|she|we|they)\s+(?:(am|are|is|was|were)\s+)?"
            r"([a-z][a-z'-]*)\s+(?:the\s+|an?\s+)?"
            r"(sentence|utterance|output|result)"
            r"(?:\s+in\s+(?:the\s+)?(translator|translation tool))?"
            r"(?:\s+for\s+(i|you|he|she|we|they|me|him|her|us|them)\s+to\s+"
            r"(reverse engineer|reverse-engineer|decipher|decode|translate))?",
            normalized,
        )
        if action:
            subject, auxiliary, verb, obj, location, purpose_subject, purpose_verb = action.groups()
            subject_root = self._english_subject_root(subject)
            verb_root = self._known_verb_root(verb)
            object_root, _ = self.lookup(obj)
            location_root, _ = self.lookup(location) if location else (None, None)
            purpose = None
            if purpose_subject and purpose_verb:
                purpose_subject_root = self._english_subject_root(purpose_subject)
                purpose_verb_root = self._known_verb_root(purpose_verb)
                if purpose_subject_root and purpose_verb_root:
                    purpose = (purpose_subject_root, purpose_verb_root, [object_root])
            if (
                subject_root and verb_root and object_root
                and (not location or location_root)
                and (not purpose_subject or purpose)
            ):
                return self._render_simple_frame(
                    subject_root,
                    verb_root,
                    object_roots=[object_root],
                    location_root=location_root,
                    tense_root="lo" if auxiliary in {"was", "were"} else "sa",
                    evidence_root=evidence_root,
                    purpose=purpose,
                )
        return None

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
        unsupported_superlatives = {
            "best", "worst", "fastest", "slowest", "tallest", "shortest",
            "biggest", "smallest", "newest", "oldest", "strongest", "weakest",
        }
        normalized_words = set(normalized.split())
        if "than" in normalized_words or normalized_words & unsupported_superlatives:
            return self._unsupported_fragment(english, "comparative/superlative")
        if evidential == "auto":
            evidential = "assumed"
        e = self.evidential_map.get(evidential, self.evidential_map["assumed"])
        common = self._speak_common_pattern(normalized, e)
        if common is not None:
            return common
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

        raw_words = re.findall(r"[a-z][a-z'-]*|\d+", normalized)
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
        yes_no_openers = {
            "am", "are", "is", "was", "were", "do", "does", "did", "will",
            "would", "shall", "should", "can", "could", "may", "might", "must",
            "have", "has", "had",
        }
        question = bool(tokens and tokens[0] in yes_no_openers)
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

            if tok in {"do", "does", "did", "will", "would", "shall", "should",
                       "can", "could", "may", "might", "must"}:
                if tense == "auto":
                    if tok == "did":
                        tense = "past"
                    elif tok in {"will", "would", "shall"}:
                        tense = "future"
                    elif tok in {"can", "could", "should", "may", "might", "must"}:
                        tense = "potential"
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
            known_verb = self._known_verb_root(tok)
            if known_verb:
                if verb is None:
                    verb = known_verb
                else:
                    # Second verb — could be infinitive complement "want to X"
                    # In xenari, just use the second verb as the main verb
                    # and keep the first as a modal-ish prefix
                    # For now: second verb replaces if first is "want"/"need"
                    if verb in ("glemp", "qemp") and known_verb not in ("glemp", "qemp"):
                        verb = known_verb
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
            if meaning.strip().startswith("to "):
                return True
            verb_indicators = ["motion", "— v", "/v", "verb", "action", "push", "pull", "make", "shape"]
            return any(ind in meaning for ind in verb_indicators)
        return False

    def _merge_compounds(self, words: List[str]) -> List[str]:
        """
        Merge only attested multiword English keys. Productive Xenari
        compounding belongs in generation, not in English tokenization.
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
                phrase = f"{w1} {w2}"
                if w1 not in skip_words and w2 not in skip_words and self.lookup(phrase)[0]:
                    result.append(phrase)
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
        purpose_frames = set()
        recovered_boundary = False
        for sentence in sentences:
            current = []
            saw_verb_marker = False
            for token in sentence.split():
                if saw_verb_marker and token in {"ka", "ra"} and current:
                    purpose_boundary = current[-1] == "frex"
                    if purpose_boundary:
                        current.pop()
                    frames.append(" ".join(current))
                    if purpose_boundary:
                        purpose_frames.add(len(frames))
                    current = []
                    saw_verb_marker = False
                    if not purpose_boundary:
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
            "hune": "sentence", "fona": "translator", "halbru": "reverse-engineer",
            "smite": "get", "duqe": "result", "naxru": "please",
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
            polite = False
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
                elif tok == "naxru":
                    polite = True
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
                    irregular_past = {
                        "get": "got", "go": "went", "throw": "threw",
                        "reverse-engineer": "reverse-engineered",
                    }
                    if base in irregular_past:
                        base = irregular_past[base]
                    elif base.endswith("e"):
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
            if polite:
                text = f"{text}, please"
            if question:
                text = f"{text}?"
            if warnings:
                text += f" [warning: {'; '.join(warnings)}]"
            rendered.append(text)
        combined = []
        for index, text in enumerate(rendered):
            if index in purpose_frames and combined:
                combined[-1] += f" so that {text}"
            else:
                combined.append(text)
        result = ". ".join(combined)
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
