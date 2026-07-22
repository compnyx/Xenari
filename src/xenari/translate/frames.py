"""Reviewed forward-frame parsing and rendering helpers."""

import re

from .models import CommonPatternRequest, TranslationMatch


class ForwardFrameMixin:
    """Render explicitly supported clause and target-language frames."""

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
        copular_quality = self._parse_copular_quality_clause(clean, evidence_root)
        if copular_quality:
            return copular_quality
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

        # Canon causal/concessive subordination: su MARKER [subordinate] ti [main].
        initial_relation = re.fullmatch(
            r"(because|although|even though)\s+(.+?),\s*(.+)", clean,
        )
        if initial_relation:
            relation, subordinate_text, main_text = initial_relation.groups()
            subordinate = self._parse_reviewed_clause(subordinate_text, evidence_root)
            main = self._parse_reviewed_clause(main_text, evidence_root)
            marker_root = "troz" if relation == "because" else "truq"
            if subordinate and main:
                return f"su {marker_root} {subordinate} ti {main}"
            if main:
                return self._partial_frame(
                    main,
                    f"unsupported {relation} clause: {subordinate_text}",
                )
            return self._partial_frame("", f"unsupported subordinate clause: {clean}")

        trailing_relation = re.fullmatch(
            r"(.+?)\s+(because|although|even though)\s+(.+)", clean,
        )
        if trailing_relation:
            main_text, relation, subordinate_text = trailing_relation.groups()
            main = self._parse_reviewed_clause(main_text, evidence_root)
            subordinate = self._parse_reviewed_clause(subordinate_text, evidence_root)
            marker_root = "troz" if relation == "because" else "truq"
            if subordinate and main:
                return f"su {marker_root} {subordinate} ti {main}"
            if main:
                return self._partial_frame(
                    main,
                    f"unsupported {relation} clause: {subordinate_text}",
                )
            return self._partial_frame("", f"unsupported subordinate clause: {clean}")

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
        """Run common-frame recognizers in their established precedence."""
        request = CommonPatternRequest(normalized, evidence_root, terminal_question)
        stages = (
            self._match_common_fixed_patterns,
            self._match_common_reviewed_patterns,
            self._match_common_predicate_patterns,
        )
        for stage in stages:
            rendered = stage(request)
            if rendered is not None:
                return TranslationMatch(stage.__name__, rendered).text
        return None

    def _match_common_fixed_patterns(self, request: CommonPatternRequest):
        """Match fixed prompts and explicit translation-target frames."""
        normalized = request.normalized
        evidence_root = request.evidence_root
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
        return None

    def _match_common_reviewed_patterns(self, request: CommonPatternRequest):
        """Match reviewed imperative, modifier, and intransitive frames."""
        normalized = request.normalized
        evidence_root = request.evidence_root
        terminal_question = request.terminal_question
        interrogative_roots = {
            "what": "qan", "which": "qan", "where": "qur", "how": "cil", "why": "voq",
        }
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
        return None

    def _match_common_predicate_patterns(self, request: CommonPatternRequest):
        """Match explicit copula, perfect, modal, and action predicates."""
        normalized = request.normalized
        evidence_root = request.evidence_root
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
