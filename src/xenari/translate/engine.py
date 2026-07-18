import re

from .dialogue import DialogueTranslationMixin
from .frames import ForwardFrameMixin
from .models import ForwardClauseRequest, ForwardClauseState, TranslationMatch
from .modifiers import ModifierTranslationMixin
from .numbers import NumberTranslationMixin
from .preprocessing import EnglishPreprocessingMixin
from .reverse import ReverseTranslationMixin


class TranslatorMixin(
    EnglishPreprocessingMixin,
    ForwardFrameMixin,
    NumberTranslationMixin,
    ModifierTranslationMixin,
    DialogueTranslationMixin,
    ReverseTranslationMixin,
):
    def speak(self, english: str, tense: str = "auto", evidential: str = "auto") -> str:
        """Translate English as a sequence of bounded clauses.

        The compact clause translator below is intentionally conservative.  It
        is safer to expose an untranslated fragment than to print an English
        token in a position where it would look like a coined Xenari root.
        """
        number_math = self._speak_number_or_math(english)
        if number_math is not None:
            return number_math
        whole_phrase = self._casual_phrase(english)
        if whole_phrase is not None:
            return whole_phrase
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
            clause, temporal_root = self._split_sentence_final_temporal(clause)
            xenari = self._speak_clause(clause, tense=tense, evidential=evidential)
            if not xenari:
                continue
            if temporal_root and not xenari.startswith(("[untranslated:", "[partial:")):
                xenari = f"{xenari} {temporal_root}"
            connector_root = connector_roots.get(connector or "")
            if connector_root and not xenari.startswith("[untranslated:"):
                xenari = f"{connector_root} {xenari}"
            rendered.append(xenari)
        return ". ".join(rendered) if rendered else "[untranslated: no translatable content]"

    def _speak_clause(self, english: str, tense: str = "auto", evidential: str = "auto") -> str:
        """Build one OSV clause through ordered bounded translation stages."""
        request = self._prepare_clause_request(english, tense, evidential)
        match = self._dispatch_clause_request(request)
        if match is not None:
            return match.text
        return self._speak_generic_clause(request)

    def _prepare_clause_request(
        self,
        english: str,
        tense: str,
        evidential: str,
    ) -> ForwardClauseRequest:
        """Normalize one clause and resolve its non-lexical context."""
        terminal_question = english.strip().endswith("?")
        normalized = re.sub(r"[^a-z0-9' ]+", " ", english.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        first_word = normalized.split(maxsplit=1)[0] if normalized else ""
        terminal_yes_no_question = terminal_question and first_word not in {
            "what", "which", "where", "when", "how", "why", "who", "whom", "whose",
        }
        if evidential == "auto":
            if re.search(r"\bsaw\b", normalized):
                evidential = "witnessed"
            elif re.search(r"\bheard\b", normalized):
                evidential = "reported"
            else:
                evidential = "assumed"
        evidence_root = self.evidential_map.get(evidential, self.evidential_map["assumed"])
        return ForwardClauseRequest(
            source=english,
            normalized=normalized,
            tense=tense,
            evidential=evidential,
            evidence_root=evidence_root,
            terminal_question=terminal_question,
            terminal_yes_no_question=terminal_yes_no_question,
        )

    def _dispatch_clause_request(
        self,
        request: ForwardClauseRequest,
    ) -> TranslationMatch | None:
        """Run specialized clause recognizers in their established order."""
        english = request.source
        normalized = request.normalized
        evidence_root = request.evidence_root

        number_math = self._speak_number_or_math(english)
        if number_math is not None:
            return TranslationMatch("number-or-math", number_math)
        infinitive_complement = re.fullmatch(
            r"(i|you|he|she|we|they)\s+(want|wants|wanted|need|needs|needed)\s+to\s+(.+)",
            normalized,
        )
        if infinitive_complement:
            subject, matrix_verb, complement = infinitive_complement.groups()
            return TranslationMatch(
                "unsupported-infinitive",
                self._partial_frame(
                    "",
                    f"unsupported infinitive complement retained: {subject} {matrix_verb} to {complement}",
                ),
            )
        casual_phrase = self._casual_phrase(english)
        if casual_phrase is not None:
            return TranslationMatch("casual-phrase", casual_phrase)
        clause_frame = self._speak_clause_frame(english, evidence_root)
        if clause_frame is not None:
            return TranslationMatch("clause-frame", clause_frame)
        dialogue_frame = self._speak_dialogue_frame(english, evidence_root)
        if dialogue_frame is not None:
            return TranslationMatch("dialogue-frame", dialogue_frame)
        # Target-language commands are a supported imperative subset, so they
        # must precede the generic unsupported-imperative fallback.
        imperative_translation = self._speak_target_language_imperative(normalized, evidence_root)
        if imperative_translation is not None:
            return TranslationMatch("target-language-imperative", imperative_translation)
        guarded_fragment = self._speak_guarded_fragment(english, evidence_root)
        if guarded_fragment is not None:
            return TranslationMatch("guarded-fragment", guarded_fragment)
        modifier_frame = self._speak_modifier_frame(english, evidence_root)
        if modifier_frame is not None:
            return TranslationMatch("modifier-frame", modifier_frame)
        unsupported_superlatives = {
            "best", "worst", "fastest", "slowest", "tallest", "shortest",
            "biggest", "smallest", "newest", "oldest", "strongest", "weakest",
        }
        normalized_words = set(normalized.split())
        if "than" in normalized_words or normalized_words & unsupported_superlatives:
            return TranslationMatch(
                "unsupported-comparison",
                self._unsupported_fragment(english, "comparative/superlative"),
            )
        first_word = normalized.split(maxsplit=1)[0] if normalized else ""
        if first_word in {"who", "whom", "whose"}:
            return TranslationMatch(
                "unsupported-wh-subject",
                self._unsupported_fragment(
                    english,
                    f"WH subject '{first_word}' lacks a canon interrogative",
                ),
            )
        if first_word == "when":
            return TranslationMatch(
                "unsupported-when",
                self._unsupported_fragment(
                    english,
                    "WH/temporal 'when' lacks a proven shared frame",
                ),
            )
        common = self._speak_common_pattern(
            normalized,
            evidence_root,
            terminal_question=request.terminal_yes_no_question,
        )
        if common is not None:
            return TranslationMatch("common-pattern", common)
        exact_phrases = {
            "you little bitch": "mex krengk frem",
            "my hat blows off": f"ra neq po brid ka vi cuq ta qruq vi sa {evidence_root}",
            "the figure's hat blows off": f"ra vi loco po brid ka vi cuq ta qruq vi sa {evidence_root}",
            "i approach the figure by the lake": f"ra vi loco na nu qlon ka neq ta frig sa {evidence_root}",
            "i see the alien in the forest": f"ra vi qex na nu canq ka neq ta toq sa {evidence_root}",
            "creative work": "flonx",
            "creative art": "flonx",
        }
        if normalized in exact_phrases:
            return TranslationMatch("exact-phrase", exact_phrases[normalized])
        if normalized == "i approach the figure by the lake the figure's hat blows off":
            return TranslationMatch(
                "exact-multiclause",
                f"ra vi loco na nu qlon ka neq ta frig sa {evidence_root}. "
                f"ra vi loco po brid ka vi cuq ta qruq vi sa {evidence_root}",
            )

        working_match = re.fullmatch(
            r"(?:the\s+)?([a-z][a-z'-]*)\s+(is|are|was|were)\s+not\s+working",
            normalized,
        )
        if working_match:
            subject_word, auxiliary = working_match.groups()
            subject_root, _ = self.lookup(subject_word)
            if not subject_root:
                return TranslationMatch(
                    "working-unknown-subject",
                    self._untranslated_fragment(english, [subject_word]),
                )
            subject_animacy = self._animacy_for(subject_root, default=self.p["inan"])
            tense_root = self.p["past"] if auxiliary in {"was", "were"} else self.p["pres"]
            return TranslationMatch(
                "negative-working",
                f"ka {subject_animacy} {subject_root} ta qxundraz "
                f"{subject_animacy} {tense_root} {evidence_root} {self.p['neg']}",
            )
        return None

    def _classify_generic_tokens(
        self,
        tokens: list[str],
        request: ForwardClauseRequest,
    ) -> ForwardClauseState:
        """Classify generic tokens without rendering their final OSV frame."""
        yes_no_openers = {
            "am", "are", "is", "was", "were", "do", "does", "did", "will",
            "would", "shall", "should", "can", "could", "may", "might", "must",
            "have", "has", "had",
        }
        state = ForwardClauseState(
            tense=request.tense,
            evidential=request.evidential,
            question=(
                request.terminal_yes_no_question
                or bool(tokens and tokens[0] in yes_no_openers)
            ),
        )
        if state.tense == "auto" and any(
            token in {
                "built", "said", "touched", "slammed", "stopped", "broke", "broken",
                "whispered", "heard", "kissed", "loved",
            }
            for token in tokens
        ):
            state.tense = "past"

        wh_roots = {
            "what": "qan", "which": "qan", "where": "qur", "how": "cil", "why": "voq",
        }
        for index, token in enumerate(tokens):
            if token in self.en_pronouns:
                pronoun = self.en_pronouns[token]
                ordinal = pronoun[0]
                is_possessive = pronoun[1]
                is_plural = len(pronoun) > 2 and pronoun[2]
                if state.subject is None:
                    state.subject = self.pronouns[ordinal]
                    state.subject_plural = is_plural
                elif state.object is None:
                    state.object = self.pronouns[ordinal]
                    state.object_possessive = is_possessive
                continue

            if token in ("not", "no", "never", "dont", "doesnt", "didnt", "wont", "cant", "cannot"):
                state.negated = True
                continue

            if token in {"have", "has", "had", "having"}:
                if state.tense == "auto" and token == "had":
                    state.tense = "past"
                continue

            if token in {
                "do", "does", "did", "will", "would", "shall", "should",
                "can", "could", "may", "might", "must",
            }:
                if state.tense == "auto":
                    if token == "did":
                        state.tense = "past"
                    elif token in {"will", "would", "shall"}:
                        state.tense = "future"
                    elif token in {"can", "could", "should", "may", "might", "must"}:
                        state.tense = "potential"
                continue

            if token in wh_roots:
                state.interrogative_root = wh_roots[token]
                continue
            if token == "when":
                continue

            if (
                token == "to"
                and index + 1 < len(tokens)
                and (
                    tokens[index + 1] in self.verb_map
                    or self._is_verb_like(tokens[index + 1])
                )
            ):
                continue
            if token in self.skip_words:
                continue

            if state.tense == "auto":
                if token in ("was", "were", "had", "did", "ed"):
                    state.tense = "past"
                elif token in ("will", "shall", "would"):
                    state.tense = "future"
                elif token in ("usually", "often", "always"):
                    state.tense = "habitual"
                elif token in ("could", "might", "may"):
                    state.tense = "potential"

            if token == "saw":
                state.evidential = "witnessed"
            elif token == "heard":
                state.evidential = "reported"

            known_verb = self._known_verb_root(token)
            if known_verb:
                if state.verb is None:
                    state.verb = known_verb
                elif (
                    state.verb in ("glemp", "qemp")
                    and known_verb not in ("glemp", "qemp")
                ):
                    state.verb = known_verb
                continue
            if token in self.copula_words:
                state.copula = True
                continue

            root, _ = self.lookup(token)
            if root and self._is_verb_like(token):
                if state.verb is None:
                    state.verb = root
                continue

            if root:
                if state.subject is not None and state.verb is not None:
                    if state.object is None:
                        state.object = root
                    else:
                        state.object_roots.append(root)
                elif state.subject is not None and state.verb is None:
                    if self._is_verb_like(token):
                        state.verb = root
                    elif state.object is None:
                        state.object = root
                    else:
                        state.object_roots.append(root)
                elif state.object is None:
                    state.object = root
                else:
                    state.object_roots.append(root)
            else:
                state.unknown_words.append(token)
        return state

    def _speak_generic_clause(self, request: ForwardClauseRequest) -> str:
        """Classify and render the conservative generic English clause path."""
        english = request.source
        normalized = request.normalized

        raw_words = re.findall(r"[a-z][a-z'-]*|\d+", normalized)
        if not raw_words:
            return ""

        # Phase 1: detect and merge compounds (2-word scan)
        tokens = self._merge_compounds(raw_words)

        state = self._classify_generic_tokens(tokens, request)
        tense = state.tense
        evidential = state.evidential
        subj = state.subject
        subj_plural = state.subject_plural
        obj = state.object
        obj_possessive = state.object_possessive
        verb = state.verb
        copula = state.copula
        negated = state.negated
        question = state.question
        interrogative_root = state.interrogative_root
        obj_tokens = state.object_roots
        unknown_words = state.unknown_words

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

        if subj is None and (verb or copula):
            return self._unsupported_fragment(
                english,
                "clause subject could not be established safely",
            )

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

        if interrogative_root:
            result = f"{interrogative_root} {result}".strip()

        # Question particle
        if question:
            result += f" {self.p['q']}"

        # Flag unknowns
        if "[unknown" in result:
            missing = re.findall(r"\[unknown:([^\]]+)\]", result)
            result += f"  [missing: {', '.join(missing)}]"

        return result

    def gloss(self, english: str, tense: str = "auto", evidential: str = "auto") -> str:
        """Return Xenari + rough English gloss."""
        xen = self.speak(english, tense, evidential)
        return f"{xen}\n  (rough) {english}"

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
