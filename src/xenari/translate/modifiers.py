import re


class ModifierTranslationMixin:
    def _parse_modifier_np(self, english: str):
        """Parse one bounded possessive/quantity/modifier noun phrase.

        This deliberately uses the reviewed canon roots instead of whichever
        noisy English mapping happens to win a broad dictionary lookup.
        """
        clean = re.sub(r"\s+", " ", english.strip().lower())
        clean = re.sub(r"^(?:the|a|an)\s+", "", clean)
        if not clean:
            return None

        possessor_root = None
        possessor_plural = False
        possessive_pronouns = {
            "my": (self.pronouns["1"], False),
            "our": (self.pronouns["1"], True),
            "your": (self.pronouns["2"], False),
            "his": (self.pronouns["3"], False),
            "her": (self.pronouns["3"], False),
            "its": (self.pronouns["3"], False),
            "their": (self.pronouns["4"], True),
        }
        first, separator, remainder = clean.partition(" ")
        if first in possessive_pronouns and separator:
            possessor_root, possessor_plural = possessive_pronouns[first]
            clean = remainder
        else:
            possessive = re.fullmatch(
                r"(?:the\s+)?([a-z][a-z'-]*?)(?:'s|s')\s+(.+)", clean,
            )
            if possessive:
                owner_word, clean = possessive.groups()
                possessor_root = self._english_subject_root(owner_word)
                if not possessor_root:
                    return None

        demonstrative_root = None
        first, separator, remainder = clean.partition(" ")
        if first in {"this", "that"} and separator:
            demonstrative_root = {"this": "praq", "that": "zra"}[first]
            clean = remainder

        words = clean.split()
        if not words:
            return None

        quantifier_roots = {
            "one": "fqam", "many": "xant", "all": "qrunq",
            "some": "frox", "no": "nulxant", "few": "klog",
            "each": "cleg", "every": "cleg",
        }
        quality_roots = {
            "red": "rlis", "big": "nyix", "good": "nax", "bad": "qez",
            "fast": "kag", "tall": "sump", "small": "frem",
            "dangerous": "fatyih",
        }
        superlative_roots = {
            "fastest": "kag", "best": "nax", "worst": "qez",
            "biggest": "nyix", "tallest": "sump", "smallest": "frem",
        }

        quantifier_root = None
        number_parts = None
        qualities = []
        saw_superlative = False
        modifiers = words[:-1]
        for word in modifiers:
            if word in quantifier_roots and quantifier_root is None:
                quantifier_root = quantifier_roots[word]
            elif number_parts is None and (value := self._parse_english_number_value(word)) is not None:
                # `one` remains the ordinary quantifier `fqam` above. Other
                # numerals use productive base-6 composition (`six` -> ca xang).
                number_parts = self._base6_number_parts(value)
            elif word in quality_roots:
                qualities.append(quality_roots[word])
            elif word in superlative_roots and not saw_superlative:
                qualities.append(superlative_roots[word])
                saw_superlative = True
            else:
                return None

        head_word = words[-1]
        # Resolve attested lexical plurals before trying a guessed singular.
        # For example, "glasses" and "glass" name different canon roots.
        lexical_plurals = {"glasses", "pants", "shorts"}
        plural = head_word in lexical_plurals
        head_root = self._english_subject_root(head_word)
        if not head_root and head_word not in self.en_pronouns and head_word != "people":
            singular_candidates = []
            if head_word.endswith("ies") and len(head_word) > 3:
                singular_candidates.append(head_word[:-3] + "y")
            if head_word.endswith("es") and len(head_word) > 2:
                singular_candidates.append(head_word[:-2])
            if head_word.endswith("s") and len(head_word) > 1:
                singular_candidates.append(head_word[:-1])
            for candidate in singular_candidates:
                candidate_root = self._english_subject_root(candidate)
                if candidate_root:
                    head_word, head_root, plural = candidate, candidate_root, True
                    break
        if not head_root:
            return None

        if head_word in self.en_pronouns:
            pinfo = self.en_pronouns[head_word]
            plural = len(pinfo) > 2 and pinfo[2]

        roots = []
        phrase_head_root = head_root
        if possessor_root:
            roots.append(possessor_root)
            if possessor_plural:
                roots.append(self.p["pl"])
            roots.extend([self.p["poss"], head_root])
            phrase_head_root = possessor_root
        else:
            roots.append(head_root)
        if demonstrative_root:
            roots.append(demonstrative_root)
        if quantifier_root:
            roots.append(quantifier_root)
        roots.extend(qualities)
        if saw_superlative:
            roots.append("qruv")
        if number_parts:
            roots.extend(number_parts)

        quantified = bool(quantifier_root or number_parts)
        featured = bool(
            possessor_root or demonstrative_root or quantifier_root or number_parts
            or qualities or plural
        )
        return {
            "roots": roots,
            "head_root": phrase_head_root,
            "animacy": self._reviewed_animacy(head_word, phrase_head_root),
            "inherent_animacy": self._is_pronoun_root(phrase_head_root),
            "plural": bool(plural and not quantified),
            "featured": featured,
            "superlative": saw_superlative,
        }

    def _render_modifier_np(self, noun_phrase, case=None):
        if not noun_phrase:
            return None
        parts = []
        if case:
            parts.append(case)
            if not noun_phrase["inherent_animacy"]:
                parts.append(noun_phrase["animacy"])
        parts.extend(noun_phrase["roots"])
        if noun_phrase["plural"]:
            parts.append(self.p["pl"])
        return parts

    def _render_modifier_clause(
        self,
        subject_phrase,
        verb_word: str,
        *,
        object_phrase=None,
        evidence_root="xo",
        include_tense=True,
        tense_root=None,
        negated=False,
        question=False,
    ):
        verb_root = self._known_verb_root(verb_word)
        if not subject_phrase or not verb_root:
            return None
        parts = []
        if object_phrase:
            parts.extend(self._render_modifier_np(object_phrase, "ra"))
        parts.extend(self._render_modifier_np(subject_phrase, "ka"))
        parts.extend(["ta", verb_root])
        if not subject_phrase["inherent_animacy"]:
            parts.append(subject_phrase["animacy"])
        if include_tense:
            if tense_root is None:
                past_forms = {
                    "ate", "bit", "broke", "built", "entered", "found", "gave",
                    "heard", "helped", "kissed", "loved", "opened", "ran", "rested", "sat", "saw", "sent",
                    "slammed", "slept", "stood", "stopped", "took", "touched",
                    "waited", "walked", "went",
                }
                tense_root = "lo" if verb_word in past_forms else "sa"
            parts.extend([tense_root, evidence_root])
        if negated:
            parts.append(self.p["neg"])
        if question:
            parts.append(self.p["q"])
        return " ".join(parts)

    def _parse_modifier_clause(self, english: str, evidence_root: str, require_feature=True):
        """Parse a simple clause only when reviewed modifier semantics are present."""
        clean = re.sub(r"\s+", " ", english.strip().lower())
        verb_forms = (
            "see|sees|saw|build|builds|built|open|opens|opened|help|helps|helped|"
            "find|finds|found|touch|touched|hear|hears|heard|bite|bites|bit|"
            "love|loves|loved|translate|translates|translated|eat|eats|ate|"
            "send|sends|sent|give|gives|gave|take|takes|took"
        )
        going_to_transitive = re.fullmatch(
            rf"(.+?)\s+(am|are|is|was|were)\s+(not\s+)?going\s+to\s+"
            rf"({verb_forms})\s+(.+)",
            clean,
        )
        if going_to_transitive:
            subject_text, auxiliary, negation, verb_word, object_text = going_to_transitive.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            object_phrase = self._parse_modifier_np(object_text)
            if subject_phrase and object_phrase:
                return self._render_modifier_clause(
                    subject_phrase,
                    verb_word,
                    object_phrase=object_phrase,
                    evidence_root=evidence_root,
                    tense_root="ve",
                    negated=bool(negation),
                    question=False,
                )

        aux_question_transitive = re.fullmatch(
            rf"(do|does|did|will|can|could)\s+(.+?)\s+(not\s+)?"
            rf"({verb_forms})\s+(.+)",
            clean,
        )
        if aux_question_transitive:
            auxiliary, subject_text, negation, verb_word, object_text = aux_question_transitive.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            object_phrase = self._parse_modifier_np(object_text)
            if subject_phrase and object_phrase:
                tense_root = (
                    "lo" if auxiliary == "did"
                    else "ve" if auxiliary == "will"
                    else "pe" if auxiliary in {"can", "could"}
                    else "sa"
                )
                return self._render_modifier_clause(
                    subject_phrase,
                    verb_word,
                    object_phrase=object_phrase,
                    evidence_root=evidence_root,
                    tense_root=tense_root,
                    negated=bool(negation),
                    question=True,
                )

        aux_transitive = re.fullmatch(
            rf"(.+?)\s+(do|does|did|will|can|could)\s+(not\s+)?"
            rf"({verb_forms})\s+(.+)",
            clean,
        )
        if aux_transitive:
            subject_text, auxiliary, negation, verb_word, object_text = aux_transitive.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            object_phrase = self._parse_modifier_np(object_text)
            if subject_phrase and object_phrase:
                tense_root = (
                    "lo" if auxiliary == "did"
                    else "ve" if auxiliary == "will"
                    else "pe" if auxiliary in {"can", "could"}
                    else "sa"
                )
                return self._render_modifier_clause(
                    subject_phrase,
                    verb_word,
                    object_phrase=object_phrase,
                    evidence_root=evidence_root,
                    tense_root=tense_root,
                    negated=bool(negation),
                    question=False,
                )

        transitive = re.fullmatch(rf"(.+?)\s+({verb_forms})\s+(.+)", clean)
        if transitive:
            subject_text, verb_word, object_text = transitive.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            object_phrase = self._parse_modifier_np(object_text)
            if subject_phrase and object_phrase and (
                not require_feature
                or subject_phrase["featured"]
                or object_phrase["featured"]
            ):
                return self._render_modifier_clause(
                    subject_phrase,
                    verb_word,
                    object_phrase=object_phrase,
                    evidence_root=evidence_root,
                )

        intransitive = re.fullmatch(
            r"(.+?)\s+"
            r"(open|opens|opened|run|runs|ran|wait|waits|waited|"
            r"enter|enters|entered|stop|stops|stopped|slam|slams|slammed|"
            r"walk|walks|walked|sleep|sleeps|slept|rest|rests|rested|"
            r"sit|sits|sat|stand|stands|stood)"
            r"(?:\s+(?:quickly|slowly|quietly|loudly))?",
            clean,
        )
        if intransitive:
            subject_text, verb_word = intransitive.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            if subject_phrase and (not require_feature or subject_phrase["featured"]):
                return self._render_modifier_clause(
                    subject_phrase, verb_word, evidence_root=evidence_root,
                )
        aux_question_intransitive = re.fullmatch(
            r"(do|does|did|will|can|could)\s+(.+?)\s+(not\s+)?"
            r"(open|opens|opened|run|runs|ran|wait|waits|waited|"
            r"enter|enters|entered|stop|stops|stopped|walk|walks|walked|"
            r"sleep|sleeps|slept|rest|rests|rested|sit|sits|sat|"
            r"stand|stands|stood)",
            clean,
        )
        if aux_question_intransitive:
            auxiliary, subject_text, negation, verb_word = aux_question_intransitive.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            if subject_phrase:
                tense_root = (
                    "lo" if auxiliary == "did"
                    else "ve" if auxiliary == "will"
                    else "pe" if auxiliary in {"can", "could"}
                    else "sa"
                )
                return self._render_modifier_clause(
                    subject_phrase,
                    verb_word,
                    evidence_root=evidence_root,
                    tense_root=tense_root,
                    negated=bool(negation),
                    question=True,
                )
        aux_intransitive = re.fullmatch(
            r"(.+?)\s+(do|does|did|will|can|could)\s+(not\s+)?"
            r"(open|opens|opened|run|runs|ran|wait|waits|waited|"
            r"enter|enters|entered|stop|stops|stopped|walk|walks|walked|"
            r"sleep|sleeps|slept|rest|rests|rested|sit|sits|sat|"
            r"stand|stands|stood)",
            clean,
        )
        if aux_intransitive:
            subject_text, auxiliary, negation, verb_word = aux_intransitive.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            if subject_phrase:
                tense_root = (
                    "lo" if auxiliary == "did"
                    else "ve" if auxiliary == "will"
                    else "pe" if auxiliary in {"can", "could"}
                    else "sa"
                )
                return self._render_modifier_clause(
                    subject_phrase,
                    verb_word,
                    evidence_root=evidence_root,
                    tense_root=tense_root,
                    negated=bool(negation),
                    question=False,
                )
        progressive = re.fullmatch(
            r"(.+?)\s+(is|are|was|were)\s+(not\s+)?([a-z][a-z'-]*ing)",
            clean,
        )
        if progressive:
            subject_text, auxiliary, negation, verb_word = progressive.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            if subject_phrase and self._known_verb_root(verb_word):
                return self._render_modifier_clause(
                    subject_phrase,
                    verb_word,
                    evidence_root=evidence_root,
                    tense_root="lo" if auxiliary in {"was", "were"} else "sa",
                    negated=bool(negation),
                )
        return None

    def _speak_modifier_frame(self, english: str, evidence_root: str):
        """Handle reviewed comparison, superlative, possession, and quantity frames."""
        clean = re.sub(r"[.!?]+$", "", english.strip().lower())
        clean = re.sub(r"\s+", " ", clean)

        comparative_roots = {
            "taller": "sump", "bigger": "nyix", "better": "nax",
            "worse": "qez", "faster": "kag", "smaller": "frem",
        }
        comparative = re.fullmatch(
            r"(.+?)\s+(is|are|was|were)\s+([a-z]+)\s+than\s+(.+)", clean,
        )
        if comparative:
            subject_text, auxiliary, quality_word, standard_text = comparative.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            standard_phrase = self._parse_modifier_np(standard_text)
            quality_root = comparative_roots.get(quality_word)
            if subject_phrase and standard_phrase and quality_root:
                parts = ["ra", quality_root, "maq"]
                parts.extend(self._render_modifier_np(subject_phrase, "ka"))
                parts.extend(["ta", "zux"])
                if not subject_phrase["inherent_animacy"]:
                    parts.append(subject_phrase["animacy"])
                parts.extend([
                    "lo" if auxiliary in {"was", "were"} else "sa",
                    evidence_root,
                ])
                rendered = " ".join(parts)
                return self._partial_frame(
                    rendered,
                    f"than {standard_text} preserved; comparison-standard canon conflict",
                )

        copular_superlative = re.fullmatch(
            r"(this|that)\s+(is|was)\s+(.+)", clean,
        )
        if copular_superlative:
            subject_word, auxiliary, predicate_text = copular_superlative.groups()
            predicate_phrase = self._parse_modifier_np(predicate_text)
            subject_root = {"this": "praq", "that": "zra"}[subject_word]
            if predicate_phrase and predicate_phrase["superlative"]:
                subject_phrase = {
                    "roots": [subject_root],
                    "head_root": subject_root,
                    "animacy": self.p["inan"],
                    "inherent_animacy": False,
                    "plural": False,
                }
                parts = self._render_modifier_np(predicate_phrase, "ra")
                parts.extend(self._render_modifier_np(subject_phrase, "ka"))
                parts.extend([
                    "ta", "zux", self.p["inan"],
                    "lo" if auxiliary == "was" else "sa", evidence_root,
                ])
                return " ".join(parts)

        quality_roots = {
            "red": "rlis", "big": "nyix", "good": "nax", "nice": "naxu",
            "bad": "qez", "fast": "kag", "tall": "sump", "small": "frem",
            "dangerous": "fatyih", "open": "xleq", "closed": "qrak",
        }
        copular_quality = re.fullmatch(
            r"(is|are|was|were)\s+(.+?)\s+(not\s+)?([a-z][a-z'-]*)",
            clean,
        )
        if copular_quality:
            auxiliary, subject_text, negation, quality_word = copular_quality.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            quality_root = quality_roots.get(quality_word)
            if subject_phrase and quality_root:
                parts = ["ra", quality_root]
                parts.extend(self._render_modifier_np(subject_phrase, "ka"))
                parts.extend(["ta", "zux"])
                if not subject_phrase["inherent_animacy"]:
                    parts.append(subject_phrase["animacy"])
                parts.extend([
                    "lo" if auxiliary in {"was", "were"} else "sa",
                    evidence_root,
                    self.p["q"],
                ])
                if negation:
                    parts.append(self.p["neg"])
                return " ".join(parts)
        copular_quality = re.fullmatch(
            r"(.+?)\s+(is|are|was|were)\s+(not\s+)?([a-z][a-z'-]*)",
            clean,
        )
        if copular_quality:
            subject_text, auxiliary, negation, quality_word = copular_quality.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            quality_root = quality_roots.get(quality_word)
            if subject_phrase and quality_root:
                parts = ["ra", quality_root]
                parts.extend(self._render_modifier_np(subject_phrase, "ka"))
                parts.extend(["ta", "zux"])
                if not subject_phrase["inherent_animacy"]:
                    parts.append(subject_phrase["animacy"])
                parts.extend(["lo" if auxiliary in {"was", "were"} else "sa", evidence_root])
                if negation:
                    parts.append(self.p["neg"])
                return " ".join(parts)

        purpose = re.fullmatch(
            r"(i|you|he|she|we)\s+(opened|built|touched)\s+(.+?)\s+to\s+"
            r"(help|touch|open)\s+(i|you|he|she|we|me|him|us)",
            clean,
        )
        if purpose:
            subject_text, verb_word, object_text, purpose_verb, purpose_object_text = purpose.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            object_phrase = self._parse_modifier_np(object_text)
            purpose_object = self._parse_modifier_np(purpose_object_text)
            if (
                subject_phrase and object_phrase and purpose_object
                and object_phrase["featured"]
            ):
                main = self._render_modifier_clause(
                    subject_phrase,
                    verb_word,
                    object_phrase=object_phrase,
                    evidence_root=evidence_root,
                )
                purpose_clause = self._render_modifier_clause(
                    subject_phrase,
                    purpose_verb,
                    object_phrase=purpose_object,
                    evidence_root=evidence_root,
                    include_tense=False,
                )
                if main and purpose_clause:
                    return f"{main} frex {purpose_clause}"

        simple_clause = self._parse_modifier_clause(clean, evidence_root)
        if simple_clause:
            return simple_clause

        possession = re.fullmatch(r"(.+?)\s+(has|have|had)\s+(.+)", clean)
        if possession:
            subject_text, verb_word, object_text = possession.groups()
            subject_phrase = self._parse_modifier_np(subject_text)
            object_phrase = self._parse_modifier_np(object_text)
            if subject_phrase and object_phrase:
                return self._render_modifier_clause(
                    subject_phrase,
                    "have",
                    object_phrase=object_phrase,
                    evidence_root=evidence_root,
                    tense_root="lo" if verb_word == "had" else "sa",
                )

        noun_phrase = self._parse_modifier_np(clean)
        if noun_phrase and noun_phrase["featured"]:
            return " ".join(self._render_modifier_np(noun_phrase))
        return None
