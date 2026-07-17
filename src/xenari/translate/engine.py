import re
from typing import List, Tuple

from .dialogue import DialogueTranslationMixin
from .modifiers import ModifierTranslationMixin
from .numbers import NumberTranslationMixin
from .reverse import ReverseTranslationMixin


class TranslatorMixin(NumberTranslationMixin, ModifierTranslationMixin, DialogueTranslationMixin, ReverseTranslationMixin):
    _sentence_final_temporals = {
        "today": "bro",
        "tomorrow": "glent",
        "yesterday": "hreh",
        "tonight": "kohfrep",
    }

    def _split_sentence_final_temporal(self, english: str):
        """Detach one reviewed trailing time word without discarding it."""
        match = re.fullmatch(
            r"(.+?)\s+(today|tomorrow|yesterday|tonight)(\s*\?)?",
            english.strip(),
            flags=re.IGNORECASE,
        )
        if not match:
            return english, None
        clause, temporal, question = match.groups()
        return clause.strip() + ("?" if question else ""), self._sentence_final_temporals[temporal.lower()]

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

    def _strip_speaker_labels(self, text: str) -> str:
        """Drop screenplay-style speaker labels before clause splitting."""
        stripped_lines = []
        label_re = re.compile(
            r"^\s*([A-Za-z][A-Za-z0-9 .'\-]{0,40}"
            r"(?:\s*\([A-Za-z0-9 .'\-]{1,12}\))?)\s*:\s*(.*)$"
        )
        for line in text.splitlines() or [text]:
            match = label_re.match(line)
            if match:
                label, rest = match.groups()
                label_core = re.sub(r"\([^)]*\)", "", label)
                if not re.search(r"[a-z]", label_core):
                    stripped_lines.append(rest)
                    continue
            stripped_lines.append(line)
        return "\n".join(stripped_lines)

    def _expand_english_contractions(self, text: str) -> str:
        contractions = {
            "i'm": "i am", "i've": "i have", "i'll": "i will", "i'd": "i would",
            "you're": "you are", "you've": "you have", "you'll": "you will", "you'd": "you would",
            "we're": "we are", "we've": "we have", "we'll": "we will", "we'd": "we would",
            "they're": "they are", "they've": "they have", "they'll": "they will", "they'd": "they would",
            "he's": "he is", "she's": "she is", "it's": "it is", "that's": "that is",
            "he'll": "he will", "she'll": "she will", "he'd": "he would", "she'd": "she would",
            "what's": "what is",
            "how's": "how is", "how're": "how are",
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
        text = self._strip_speaker_labels(text)
        expanded = self._expand_english_contractions(text)
        expanded = expanded.translate(str.maketrans({
            "“": '"', "”": '"', "„": '"', "‟": '"', "…": ".",
        }))
        # Bracketed stage directions and opening dialogue quotes are clause
        # seams.  Keeping them separate prevents their words from being
        # assigned fake roles in the adjacent spoken/narrated clause.
        expanded = re.sub(r"\[\s*([^\]\n]+?)\s*\]", r". \1. ", expanded)
        expanded = re.sub(r"\(\s*([^\)\n]+?)\s*\)", r". \1. ", expanded)
        expanded = re.sub(r"\*\s*([^*\n]+?)\s*\*", r". \1. ", expanded)
        expanded = re.sub(r":\s*", ". ", expanded)
        expanded = re.sub(r'(?<=[a-z0-9])\s+"\s*(?=[a-z0-9])', ". ", expanded)
        expanded = expanded.replace('"', " ")
        expanded = re.sub(r"\s*[—–]\s*", ". ", expanded)
        clauses: List[Tuple[str, str]] = []
        connector_words = {"and", "but", "or", "however", "once", "so", "yet"}
        greeting_tail_words = {"there", "friend", "friends", "buddy", "pal"}
        greeting_re = re.compile(r"^(hello|hey|hi|greetings)\b\s*,?\s*(.*)$")
        discourse_re = re.compile(r"^(anyway|however)\b\s*,?\s*(.*)$")
        independent_subject = re.compile(
            r"\s+(?=(?:i|you|he|she|we|they)\s+"
            r"(?:am|are|is|was|were|have|has|had|will|would|can|could|do|does|did)\b)"
        )

        for match in re.finditer(r"([^.!?]+)([.!?]+|$)", expanded):
            sentence = match.group(1).strip()
            if not sentence:
                continue
            if "?" in match.group(2):
                sentence += "?"
            # Initial condition/temporal clauses need their comma boundary in
            # order to build one canon frame instead of two unrelated clauses.
            if re.match(r"^(?:if|when|once|after|before|while)\b", sentence) and "," in sentence:
                comma_parts = [sentence]
            else:
                comma_parts = [
                    part.strip() for part in re.split(r"\s*[,;]\s*", sentence) if part.strip()
                ]
            for comma_part in comma_parts:
                connector = ""
                first, _, rest = comma_part.partition(" ")
                if first in connector_words and rest:
                    connector, comma_part = first, rest.strip()

                if re.match(r"^(?:if|when|once|after|before|while)\b.+,", comma_part):
                    clauses.append((comma_part, connector))
                    continue
                if " if " in comma_part:
                    clauses.append((comma_part, connector))
                    continue

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

                major_parts = re.split(
                    r"\s+(?=(?:and|but|or|yet)\s+"
                    r"(?:(?:i|you|he|she|we|they)\b|"
                    r"(?:the|a|an)\s+[a-z][a-z'-]*\s+[a-z][a-z'-]*\b|"
                    r"(?:open|opens|run|runs|ran|wait|waits|stop|stops)\b))"
                    r"|\s+(?=once\b)",
                    comma_part,
                )
                major_antecedent = None
                for major_index, major_part in enumerate(major_parts):
                    major_part = major_part.strip()
                    major_connector = connector if major_index == 0 else "once"
                    connector_match = re.match(r"^(and|but|or|yet)\s+(.+)$", major_part)
                    if connector_match:
                        major_connector = connector_match.group(1)
                        major_part = connector_match.group(2).strip()
                        if major_antecedent and re.fullmatch(
                            r"(?:open|opens|opened|run|runs|ran|wait|waits|waited|"
                            r"stop|stops|stopped)",
                            major_part,
                        ):
                            major_part = f"{major_antecedent} {major_part}"
                    elif major_part.startswith("once "):
                        major_connector = "once"
                        major_part = major_part[5:].strip()
                    subject_match = re.match(
                        r"^(?:the\s+|an?\s+)?"
                        r"(i|you|he|she|we|they|[a-z][a-z'-]*)\b",
                        major_part,
                    )
                    if subject_match:
                        major_antecedent = subject_match.group(1)
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

    def _phrase_key(self, english: str) -> str:
        """Normalize casual/discourse phrases before structural parsing."""
        normalized = self._expand_english_contractions(english)
        normalized = re.sub(r"[\U00010000-\U0010ffff]", " ", normalized)
        normalized = re.sub(r"[^a-z0-9' ]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _casual_phrase(self, english: str):
        key = self._phrase_key(english)
        phrases = {
            "ok": "stux",
            "okay": "stux",
            "alright": "stux",
            "all right": "stux",
            "sounds good": "naxq",
            "that sounds good": "naxq",
            "alright that sounds good": "stux. naxq",
            "all right that sounds good": "stux. naxq",
            "nice": "naxu",
            "nice sounds good": "naxu. naxq",
            "that works": "naxq",
            "works for me": "naxq",
            "fair enough": "naxq",
            "for sure": "fruxq",
            "exactly": "zug",
            "indeed": "zug",
            "right": "xrenq",
            "right now": "qros",
            "now": "qros",
            "hello": "prax",
            "hey": "prax",
            "hi": "prax",
            "greetings": "prax",
            "hello there": "prax",
            "hey there": "prax",
            "hi there": "prax",
            "hello friend": "prax",
            "hello friends": "prax",
            "hey friend": "prax",
            "hey buddy": "prax",
            "hi friend": "prax",
            "hi pal": "prax",
            "thanks": "gral",
            "thanks for solving that": "gral troz ra zra ka mex ta pyoquqab lo xo",
            "thank you": "ra mex ka neq ta gral sa xo",
            "thank you for solving that": "ra mex ka neq ta gral sa xo troz ra zra ka mex ta pyoquqab lo xo",
            "thanks a lot": "gral mse",
            "thank you very much": "gral mse",
            "much appreciated": "gral",
            "sorry": "qezxol",
            "i am sorry": "qezxol",
            "my bad": "qezxol",
            "oops": "vrin",
            "whoops": "vrin",
            "bye": "qlox'",
            "goodbye": "qlox'",
            "farewell": "qlox'",
            "see you": "qlox'",
            "take care": "qlox'",
            "see you later": "qlox' qrolo",
            "see you soon": "qlox' droh",
            "talk later": "qlox' qrolo",
            "no worries": "shengtac nulxant",
            "no problem": "shengtac nulxant",
            "not a problem": "shengtac nulxant",
            "got it": "vreqclir",
            "gotcha": "vreqclir",
            "yep": "vroq",
            "yeah": "vroq",
            "nope": "nguq",
            "nah": "nguq",
            "maybe": "vex",
            "maybe later": "vex qrolo",
            "anyway": "qzecmru",
            "english": "bivuzqa uqel po zuqra",
        }
        return phrases.get(key)










    def _english_subject_root(self, word: str):
        info = self.en_pronouns.get(word)
        if info:
            return self.pronouns[info[0]]
        root, _ = self.lookup(word)
        return root

    def _known_verb_root(self, word: str):
        """Resolve a real verb root, including common English inflections."""
        clean = word.lower().strip()
        reviewed_overrides = {
            "slams": "tulo",
            "whisper": "tyequga", "whispers": "tyequga", "whispered": "tyequga",
            "ran": "zaqa",
        }
        if clean in reviewed_overrides:
            return reviewed_overrides[clean]
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
            stem = clean[:-3]
            candidates.extend([stem, stem + "e"])
            if len(stem) > 2 and stem[-1] == stem[-2]:
                candidates.append(stem[:-1])
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
        subject_animacy=None,
    ) -> str:
        """Render a small, fully-known clause without inventing any roots."""
        parts = []
        if object_roots:
            parts.extend(["ra", "nu", *object_roots])
        if location_root:
            parts.extend(["na", "nu", location_root])
        if goal_root:
            goal_parts = list(goal_root) if isinstance(goal_root, (list, tuple)) else [goal_root]
            parts.extend(["fa", "nu", *goal_parts])
        parts.append("ka")
        subject_animacy = subject_animacy or self._animacy_for(subject_root, default=self.p["inan"])
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

    def _language_target_parts(self, target: str):
        """Return reviewed Xenari for explicit language-name targets."""
        normalized = target.lower().strip()
        if normalized == "english":
            return ["bivuzqa", "uqel", "po", "zuqra"]
        root, _ = self.lookup(normalized)
        return [root] if root else None

    def _reviewed_animacy(self, english_word: str, root: str) -> str:
        animate_words = {
            "alien", "dog", "human", "people", "person", "stranger", "woman",
        }
        if english_word.lower() in animate_words:
            return self.p["anim"]
        return self._animacy_for(root, default=self.p["inan"])

    def _reviewed_np_parts(self, case: str, english_word: str):
        """Render one reviewed one-word NP, or return None when it is unknown."""
        word = english_word.lower().strip()
        root = self._english_subject_root(word)
        if not root:
            return None
        parts = [case]
        if not self._is_pronoun_root(root):
            parts.append(self._reviewed_animacy(word, root))
        parts.append(root)
        if word in {"we", "us", "they", "them"}:
            parts.append(self.p["pl"])
        return parts






    def _render_reviewed_clause(
        self,
        subject_word: str,
        verb_word: str,
        *,
        object_word=None,
        goal_word=None,
        modal=None,
        evidence_root="xo",
        include_tense=True,
    ):
        """Render a bounded one-subject clause used by shared clause frames."""
        subject_parts = self._reviewed_np_parts("ka", subject_word)
        verb_root = self._known_verb_root(verb_word)
        if not subject_parts or not verb_root:
            return None

        parts = []
        if object_word:
            object_parts = self._reviewed_np_parts("ra", object_word)
            if not object_parts:
                return None
            parts.extend(object_parts)
        if goal_word:
            goal_parts = self._reviewed_np_parts("fa", goal_word)
            if not goal_parts:
                return None
            parts.extend(goal_parts)
        parts.extend(subject_parts)
        subject_root = self._english_subject_root(subject_word)
        parts.extend(["ta", verb_root])
        if not self._is_pronoun_root(subject_root):
            parts.append(self._reviewed_animacy(subject_word, subject_root))
        if include_tense:
            past_forms = {
                "bit", "broke", "built", "entered", "found", "helped", "opened",
                "ran", "saw", "stopped", "went",
            }
            tense_root = (
                "ve" if modal == "will"
                else "pe" if modal in {"can", "could", "would", "may", "might", "should"}
                else "lo" if verb_word in past_forms
                else "sa"
            )
            parts.extend([tense_root, evidence_root])
        return " ".join(parts)

    def _parse_reviewed_clause(self, english: str, evidence_root: str):
        """Parse only the compact reviewed SVO/SV clause shapes."""
        clean = re.sub(r"\s+", " ", english.strip().lower())
        modifier_clause = self._parse_modifier_clause(clean, evidence_root)
        if modifier_clause:
            return modifier_clause
        match = re.fullmatch(
            r"(?:the\s+|an?\s+)?([a-z][a-z'-]*)\s+"
            r"(?:(will|can|could|would|may|might|should)\s+)?"
            r"([a-z][a-z'-]*)(?:\s+(?:the\s+|an?\s+)?([a-z][a-z'-]*))?",
            clean,
        )
        if not match:
            return None
        subject, modal, verb, obj = match.groups()
        return self._render_reviewed_clause(
            subject,
            verb,
            object_word=obj,
            modal=modal,
            evidence_root=evidence_root,
        )

    def _render_relative_gap_clause(
        self,
        head_word: str,
        verb_word: str,
        object_word: str,
        evidence_root: str,
    ):
        object_phrase = self._parse_modifier_np(object_word)
        object_parts = (
            self._render_modifier_np(object_phrase, "ra")
            if object_phrase else self._reviewed_np_parts("ra", object_word)
        )
        head_root = self._english_subject_root(head_word)
        verb_root = self._known_verb_root(verb_word)
        if not object_parts or not head_root or not verb_root:
            return None
        head_animacy = self._reviewed_animacy(head_word, head_root)
        tense_root = "lo" if verb_word in {"bit", "broke", "built", "saw"} else "sa"
        return " ".join([
            *object_parts,
            "ta", verb_root, head_animacy, tense_root, evidence_root,
        ])

    @staticmethod
    def _partial_frame(rendered: str, reason: str) -> str:
        marker = f"[partial: {reason}]"
        return f"{rendered} {marker}" if rendered else marker

    def _speak_clause_frame(self, english: str, evidence_root: str):
        """Translate reviewed clause relations without claiming general coverage."""
        clean = re.sub(r"[.!?]+$", "", english.strip().lower())
        clean = re.sub(r"\s+", " ", clean)

        # Canon conditionals: pevoq [condition] ti [main].
        conditional = re.fullmatch(r"if\s+(.+?),\s*(.+)", clean)
        if conditional:
            condition_text, main_text = conditional.groups()
            condition = self._parse_reviewed_clause(condition_text, evidence_root)
            main = self._parse_reviewed_clause(main_text, evidence_root)
            if condition and main:
                return f"pevoq {condition} ti {main}"
            if main:
                return self._partial_frame(main, f"unsupported condition: if {condition_text}")
            return self._partial_frame("", f"unsupported conditional clause: {clean}")

        trailing_conditional = re.fullmatch(r"(.+?)\s+if\s+(.+)", clean)
        if trailing_conditional:
            main_text, condition_text = trailing_conditional.groups()
            main = self._parse_reviewed_clause(main_text, evidence_root)
            condition = self._parse_reviewed_clause(condition_text, evidence_root)
            if condition and main:
                return f"pevoq {condition} ti {main}"
            if main:
                reason = f"unsupported conditional clause: if {condition_text}"
                if re.fullmatch(r"(?:i|you|he|she|we|they)\s+(?:can|could|would|will)", condition_text):
                    reason += " (missing predicate)"
                return self._partial_frame(main, reason)
            return self._partial_frame("", f"unsupported conditional clause: {clean}")

        # Initial temporal subordination is distinct from an initial WH query.
        temporal = re.fullmatch(r"(when|once|after|before|while)\s+(.+?),\s*(.+)", clean)
        if temporal:
            marker, subordinate_text, main_text = temporal.groups()
            subordinate = self._parse_reviewed_clause(subordinate_text, evidence_root)
            main = self._parse_reviewed_clause(main_text, evidence_root)
            marker_root = {
                "when": "cruv", "while": "cruv", "once": "cruv",
                "after": "vrem", "before": "prexq",
            }[marker]
            if subordinate and main:
                return f"su {marker_root} {subordinate} ti {main}"
            if main:
                return self._partial_frame(
                    main,
                    f"unsupported temporal clause: {marker} {subordinate_text}",
                )
            return self._partial_frame("", f"unsupported temporal clause: {clean}")
        if re.match(r"^when\s+(?:do|does|did|will|would|can|could|is|are|was|were)\b", clean):
            return self._partial_frame("", f"unsupported WH question 'when': {clean}")

        quantified_subject_relative = re.fullmatch(
            r"the\s+([a-z][a-z'-]*)\s+(?:who|that|which)\s+"
            r"([a-z][a-z'-]*)\s+(.+?)\s+"
            r"(run|runs|ran|enter|enters|entered|stop|stops|stopped)",
            clean,
        )
        if quantified_subject_relative:
            head, relative_verb, relative_object, matrix_verb = quantified_subject_relative.groups()
            head_root = self._english_subject_root(head)
            matrix_verb_root = self._known_verb_root(matrix_verb)
            object_phrase = self._parse_modifier_np(relative_object)
            relative_clause = self._render_relative_gap_clause(
                head, relative_verb, relative_object, evidence_root,
            )
            if (
                head_root and matrix_verb_root and object_phrase
                and object_phrase["featured"] and relative_clause
            ):
                head_animacy = self._reviewed_animacy(head, head_root)
                relativizer = "zre" if head_animacy == self.p["anim"] else "vro"
                matrix_tense = "lo" if matrix_verb == "ran" else "sa"
                return " ".join([
                    "ka", head_animacy, head_root,
                    "su", relativizer, relative_clause, "ti",
                    "ta", matrix_verb_root, head_animacy, matrix_tense, evidence_root,
                ])

        # Subject-gap relative clauses with one transitive relative predicate.
        subject_relative = re.fullmatch(
            r"the\s+([a-z][a-z'-]*)\s+(?:who|that|which)\s+"
            r"([a-z][a-z'-]*)\s+(?:the\s+|an?\s+)?([a-z][a-z'-]*)\s+"
            r"([a-z][a-z'-]*)(?:\s+(?:the\s+|an?\s+)?([a-z][a-z'-]*))?",
            clean,
        )
        if subject_relative:
            head, relative_verb, relative_object, matrix_verb, matrix_object = subject_relative.groups()
            head_root = self._english_subject_root(head)
            matrix_verb_root = self._known_verb_root(matrix_verb)
            relative_clause = self._render_relative_gap_clause(
                head, relative_verb, relative_object, evidence_root,
            )
            matrix_object_parts = (
                self._reviewed_np_parts("ra", matrix_object) if matrix_object else []
            )
            if head_root and matrix_verb_root and relative_clause is not None and matrix_object_parts is not None:
                head_animacy = self._reviewed_animacy(head, head_root)
                relativizer = "zre" if head_animacy == self.p["anim"] else "vro"
                matrix_tense = "lo" if matrix_verb in {"ran"} else "sa"
                return " ".join([
                    *matrix_object_parts,
                    "ka", head_animacy, head_root,
                    "su", relativizer, relative_clause, "ti",
                    "ta", matrix_verb_root, head_animacy, matrix_tense, evidence_root,
                ])

        object_relative = re.fullmatch(
            r"(i|you|he|she|we|they)\s+([a-z][a-z'-]*)\s+the\s+"
            r"([a-z][a-z'-]*)\s+(?:who|that|which)\s+([a-z][a-z'-]*)\s+"
            r"(?:the\s+|an?\s+)?([a-z][a-z'-]*)",
            clean,
        )
        if object_relative:
            matrix_subject, matrix_verb, head, relative_verb, relative_object = object_relative.groups()
            head_root = self._english_subject_root(head)
            subject_parts = self._reviewed_np_parts("ka", matrix_subject)
            matrix_verb_root = self._known_verb_root(matrix_verb)
            relative_clause = self._render_relative_gap_clause(
                head, relative_verb, relative_object, evidence_root,
            )
            if head_root and subject_parts and matrix_verb_root and relative_clause:
                head_animacy = self._reviewed_animacy(head, head_root)
                relativizer = "zre" if head_animacy == self.p["anim"] else "vro"
                return " ".join([
                    "ra", head_animacy, head_root,
                    "su", relativizer, relative_clause, "ti",
                    *subject_parts, "ta", matrix_verb_root, "sa", evidence_root,
                ])

        copular_relative = re.fullmatch(
            r"the\s+([a-z][a-z'-]*)\s+(?:that|which)\s+is\s+"
            r"([a-z][a-z'-]*)\s+(?:belongs|belong)\s+to\s+"
            r"(i|you|he|she|we|they|me|him|her|us|them)",
            clean,
        )
        if copular_relative:
            head, quality, goal = copular_relative.groups()
            head_root = self._english_subject_root(head)
            quality_root, _ = self.lookup(quality)
            goal_parts = self._reviewed_np_parts("fa", goal)
            belong_root = self._known_verb_root("belong")
            if head_root and quality_root and goal_parts and belong_root:
                head_animacy = self._reviewed_animacy(head, head_root)
                relativizer = "zre" if head_animacy == self.p["anim"] else "vro"
                return " ".join([
                    *goal_parts,
                    "ka", head_animacy, head_root,
                    "su", relativizer, "ra", quality_root, "ta", "zux",
                    head_animacy, "sa", evidence_root, "ti",
                    "ta", belong_root, head_animacy, "sa", evidence_root,
                ])

        relative_fallback = re.match(
            r"the\s+([a-z][a-z'-]*)\s+(who|whom|that|which)\s+(.+)", clean,
        )
        if relative_fallback:
            head, relative_word, rest = relative_fallback.groups()
            head_root = self._english_subject_root(head)
            prefix = head_root or ""
            return self._partial_frame(
                prefix,
                f"unsupported relative clause: {relative_word} {rest}",
            )

        # Purpose with an explicit subject: "built X for me to translate Y".
        explicit_purpose = re.fullmatch(
            r"(i|you|he|she|we|they)\s+([a-z][a-z'-]*)\s+(?:the\s+|an?\s+)"
            r"([a-z][a-z'-]*)\s+for\s+"
            r"(i|you|he|she|we|they|me|him|her|us|them)\s+to\s+"
            r"([a-z][a-z'-]*)\s+(?:the\s+|an?\s+)?([a-z][a-z'-]*)",
            clean,
        )
        if explicit_purpose:
            subject, verb, obj, purpose_subject, purpose_verb, purpose_object = explicit_purpose.groups()
            main = self._render_reviewed_clause(
                subject, verb, object_word=obj, evidence_root=evidence_root,
            )
            purpose = self._render_reviewed_clause(
                purpose_subject,
                purpose_verb,
                object_word=purpose_object,
                evidence_root=evidence_root,
                include_tense=False,
            )
            if main and purpose:
                return f"{main} frex {purpose}"

        motion_purpose = re.fullmatch(
            r"(i|you|he|she|we|they)\s+(went|go|goes)\s+to\s+(?:the\s+|an?\s+)"
            r"([a-z][a-z'-]*)\s+to\s+([a-z][a-z'-]*)\s+"
            r"(?:the\s+|an?\s+)?([a-z][a-z'-]*)",
            clean,
        )
        if motion_purpose:
            subject, verb, goal, purpose_verb, purpose_object = motion_purpose.groups()
            main = self._render_reviewed_clause(
                subject, verb, goal_word=goal, evidence_root=evidence_root,
            )
            purpose = self._render_reviewed_clause(
                subject,
                purpose_verb,
                object_word=purpose_object,
                evidence_root=evidence_root,
                include_tense=False,
            )
            if main and purpose:
                return f"{main} frex {purpose}"

        implicit_purpose = re.fullmatch(
            r"(i|you|he|she|we|they)\s+([a-z][a-z'-]*)\s+(?:the\s+|an?\s+)"
            r"([a-z][a-z'-]*)\s+to\s+([a-z][a-z'-]*)\s+"
            r"(?:the\s+|an?\s+)?([a-z][a-z'-]*)",
            clean,
        )
        if implicit_purpose:
            subject, verb, obj, purpose_verb, purpose_object = implicit_purpose.groups()
            main = self._render_reviewed_clause(
                subject, verb, object_word=obj, evidence_root=evidence_root,
            )
            purpose = self._render_reviewed_clause(
                subject,
                purpose_verb,
                object_word=purpose_object,
                evidence_root=evidence_root,
                include_tense=False,
            )
            if main and purpose:
                return f"{main} frex {purpose}"

        return None




    def _speak_target_language_imperative(self, normalized: str, evidence_root: str):
        """Render reviewed target-language commands before imperative fallback."""
        imperative_translate = re.fullmatch(
            r"(?:(please)\s+)?"
            r"(translate|decode|decipher|reverse engineer|reverse-engineer)\s+"
            r"(?:this|that|the|an?)\s+(sentence|utterance|output|result|translation)"
            r"\s+(?:back\s+)?(?:to|into)\s+(english|xenari)(?:\s+(please))?",
            normalized,
        )
        if not imperative_translate:
            return None

        polite_before, verb, obj, target, polite_after = imperative_translate.groups()
        verb_root = self._known_verb_root(verb)
        object_root, _ = self.lookup(obj)
        target_parts = self._language_target_parts(target)
        if not (verb_root and object_root and target_parts):
            return None

        parts = ["ra", "nu", object_root, "fa", "nu", *target_parts, "ta", verb_root, "vi", "ko", evidence_root]
        if polite_before or polite_after:
            please_root, _ = self.lookup("please")
            if please_root:
                parts.append(please_root)
        return " ".join(parts)

    def _speak_common_pattern(self, normalized: str, evidence_root: str, *, terminal_question: bool = False):
        """Handle common English frames whose structure is unambiguous."""
        interrogative_roots = {
            "what": "qan", "which": "qan", "where": "qur", "how": "cil", "why": "voq",
        }
        if normalized in interrogative_roots:
            return interrogative_roots[normalized]

        if normalized == "wait":
            return f"ta {self._known_verb_root('wait')} vi ko {evidence_root}"

        if normalized == "are you there":
            subject_root = self._english_subject_root("you")
            there_root, _ = self.lookup("there")
            if subject_root and there_root:
                return self._render_simple_frame(
                    subject_root,
                    "zux",
                    object_roots=[there_root],
                    evidence_root=evidence_root,
                    question=True,
                )

        translate_target = re.fullmatch(
            r"(?:(can|could|should|will|would)\s+)?"
            r"(i|you|he|she|we|they)\s+"
            r"(translate|translates|translated|decode|decipher|reverse engineer|reverse-engineer)\s+"
            r"(?:this|that|the|an?)\s+(sentence|utterance|output|result|translation)"
            r"\s+(?:back\s+)?(?:to|into)\s+(english|xenari)(\s+please)?",
            normalized,
        )
        if translate_target:
            modal_word, subject, verb, obj, target, please = translate_target.groups()
            subject_root = self._english_subject_root(subject)
            verb_root = self._known_verb_root(verb)
            object_root, _ = self.lookup(obj)
            target_parts = self._language_target_parts(target)
            if subject_root and verb_root and object_root and target_parts:
                return self._render_simple_frame(
                    subject_root,
                    verb_root,
                    object_roots=[object_root],
                    goal_root=target_parts,
                    tense_root=(
                        "ve" if modal_word in {"will", "would"}
                        else "pe" if modal_word
                        else "lo" if verb == "translated"
                        else "sa"
                    ),
                    evidence_root=evidence_root,
                    question=bool(modal_word),
                    polite=bool(please),
                )

        imperative_translation = self._speak_target_language_imperative(normalized, evidence_root)
        if imperative_translation is not None:
            return imperative_translation

        simple_reviewed_clause = self._parse_modifier_clause(
            normalized,
            evidence_root,
            require_feature=False,
        )
        if simple_reviewed_clause:
            if terminal_question and not simple_reviewed_clause.endswith(f" {self.p['q']}"):
                return f"{simple_reviewed_clause} {self.p['q']}"
            return simple_reviewed_clause

        safe_intransitive = re.fullmatch(
            r"(?:(why)\s+did\s+)?(?:the\s+|an?\s+)?"
            r"([a-z][a-z'-]*)\s+"
            r"(open|opens|opened|run|runs|ran|wait|waits|waited|stop|stopped|slam|slams|slammed)"
            r"(?:\s+(?:quickly|slowly|quietly|loudly))?",
            normalized,
        )
        if safe_intransitive:
            interrogative, subject_word, verb_word = safe_intransitive.groups()
            subject_root, _ = self.lookup(subject_word)
            verb_root = self._known_verb_root(verb_word)
            if subject_root and verb_root:
                tense_root = "lo" if interrogative or verb_word.endswith("ed") or verb_word == "ran" else "sa"
                rendered = self._render_simple_frame(
                    subject_root,
                    verb_root,
                    tense_root=tense_root,
                    evidence_root=evidence_root,
                    subject_animacy=self._reviewed_animacy(subject_word, subject_root),
                )
                return f"{interrogative_roots[interrogative]} {rendered}" if interrogative else rendered

        going_to_work = re.fullmatch(
            r"(i|you|he|she|we|they)\s+(?:am|are|is)\s+(not\s+)?"
            r"going\s+to\s+work(?:\s+(today|tomorrow|now|right\s+now))?",
            normalized,
        )
        if going_to_work:
            subject, negated, temporal = going_to_work.groups()
            subject_root = self._english_subject_root(subject)
            job_root, _ = self.lookup("job")
            if subject_root and job_root:
                rendered = self._render_simple_frame(
                    subject_root,
                    self._known_verb_root("go"),
                    goal_root=job_root,
                    tense_root="sa" if temporal in {"now", "right now"} else "ve",
                    evidence_root=evidence_root,
                    negated=bool(negated),
                )
                temporal_root = {
                    "today": "bro",
                    "tomorrow": "glent",
                    "now": "qros",
                    "right now": "qros",
                }.get(temporal)
                return f"{rendered} {temporal_root}" if temporal_root else rendered

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
            target_root, _ = self.lookup("english") if language_target else (None, None)
            if subject_root and verb_root and object_root:
                rendered = self._render_simple_frame(
                    subject_root,
                    verb_root,
                    object_roots=[object_root],
                    goal_root=target_root,
                    tense_root="ve" if modal_word in {"will", "would"} else "pe",
                    evidence_root=evidence_root,
                    question=True,
                    polite=bool(please),
                )
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
                    tense_root=(
                        "lo"
                        if auxiliary in {"was", "were"}
                        or verb in {"built", "said", "touched", "slammed", "stopped", "broke", "broken"}
                        else "sa"
                    ),
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
            "alright": "stux",
            "all right": "stux",
            "sounds good": "naxq",
            "that sounds good": "naxq",
            "alright that sounds good": "stux. naxq",
            "all right that sounds good": "stux. naxq",
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
            "i am going to work today": f"fa nu kashatyong ka neq ta qeng ve {e} bro",
            "i am going to work": f"fa nu kashatyong ka neq ta qeng ve {e}",
            "i am going to work now": f"fa nu kashatyong ka neq ta qeng sa {e} qros",
            "i am going to work right now": f"fa nu kashatyong ka neq ta qeng sa {e} qros",
            "english": "bivuzqa uqel po zuqra",
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
