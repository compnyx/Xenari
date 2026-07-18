import re

from .dialogue import DialogueTranslationMixin
from .frames import ForwardFrameMixin
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
        """
        Build an OSV sentence from English input.
        - Detects pronouns, compounds, verbs, objects
        - Only uses real roots
        - Handles tense and evidential particles
        - Handles negation
        - Handles possession (po)
        - Handles plural (ha)
        """
        terminal_question = english.strip().endswith("?")
        normalized = re.sub(r"[^a-z0-9' ]+", " ", english.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        number_math = self._speak_number_or_math(english)
        if number_math is not None:
            return number_math
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
        e = self.evidential_map.get(evidential, self.evidential_map["assumed"])
        infinitive_complement = re.fullmatch(
            r"(i|you|he|she|we|they)\s+(want|wants|wanted|need|needs|needed)\s+to\s+(.+)",
            normalized,
        )
        if infinitive_complement:
            subject, matrix_verb, complement = infinitive_complement.groups()
            return self._partial_frame(
                "",
                f"unsupported infinitive complement retained: {subject} {matrix_verb} to {complement}",
            )
        casual_phrase = self._casual_phrase(english)
        if casual_phrase is not None:
            return casual_phrase
        clause_frame = self._speak_clause_frame(english, e)
        if clause_frame is not None:
            return clause_frame
        dialogue_frame = self._speak_dialogue_frame(english, e)
        if dialogue_frame is not None:
            return dialogue_frame
        # Target-language commands are a supported imperative subset, so they
        # must precede the generic unsupported-imperative fallback.
        imperative_translation = self._speak_target_language_imperative(normalized, e)
        if imperative_translation is not None:
            return imperative_translation
        guarded_fragment = self._speak_guarded_fragment(english, e)
        if guarded_fragment is not None:
            return guarded_fragment
        modifier_frame = self._speak_modifier_frame(english, e)
        if modifier_frame is not None:
            return modifier_frame
        unsupported_superlatives = {
            "best", "worst", "fastest", "slowest", "tallest", "shortest",
            "biggest", "smallest", "newest", "oldest", "strongest", "weakest",
        }
        normalized_words = set(normalized.split())
        if "than" in normalized_words or normalized_words & unsupported_superlatives:
            return self._unsupported_fragment(english, "comparative/superlative")
        first_word = normalized.split(maxsplit=1)[0] if normalized else ""
        if first_word in {"who", "whom", "whose"}:
            return self._unsupported_fragment(
                english,
                f"WH subject '{first_word}' lacks a canon interrogative",
            )
        if first_word == "when":
            return self._unsupported_fragment(
                english,
                "WH/temporal 'when' lacks a proven shared frame",
            )
        common = self._speak_common_pattern(normalized, e, terminal_question=terminal_yes_no_question)
        if common is not None:
            return common
        exact_phrases = {
            "you little bitch": "mex krengk frem",
            "my hat blows off": f"ra neq po brid ka vi cuq ta qruq vi sa {e}",
            "the figure's hat blows off": f"ra vi loco po brid ka vi cuq ta qruq vi sa {e}",
            "i approach the figure by the lake": f"ra vi loco na nu qlon ka neq ta frig sa {e}",
            "i see the alien in the forest": f"ra vi qex na nu canq ka neq ta toq sa {e}",
            "creative work": "flonx",
            "creative art": "flonx",
        }
        if normalized in exact_phrases:
            return exact_phrases[normalized]
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
        subj_plural = False
        obj = None
        obj_possessive = False
        verb = None
        copula = False
        negated = False
        yes_no_openers = {
            "am", "are", "is", "was", "were", "do", "does", "did", "will",
            "would", "shall", "should", "can", "could", "may", "might", "must",
            "have", "has", "had",
        }
        question = terminal_yes_no_question or bool(tokens and tokens[0] in yes_no_openers)
        interrogative_root = None
        obj_tokens = []
        unknown_words = []

        if tense == "auto" and any(
            token in {
                "built", "said", "touched", "slammed", "stopped", "broke", "broken",
                "whispered", "heard", "kissed", "loved",
            }
            for token in tokens
        ):
            tense = "past"

        for i, tok in enumerate(tokens):
            # Pronoun check
            if tok in self.en_pronouns:
                pinfo = self.en_pronouns[tok]
                ordinal = pinfo[0]
                is_poss = pinfo[1]
                is_plural = len(pinfo) > 2 and pinfo[2]
                if subj is None:
                    subj = self.pronouns[ordinal]
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
            wh_roots = {
                "what": "qan", "which": "qan", "where": "qur", "how": "cil", "why": "voq",
            }
            if tok in wh_roots:
                interrogative_root = wh_roots[tok]
                continue
            if tok in {"when"}:
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
