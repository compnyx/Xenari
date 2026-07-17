import re


class DialogueTranslationMixin:
    def _render_reviewed_imperative(
        self,
        verb_word: str,
        object_word: str | None,
        *,
        evidence_root: str,
        negated: bool,
        polite: bool,
    ) -> str | None:
        """Render one reviewed command with the canon imperative frame."""
        allowed_objects = {
            "wait": {None},
            "listen": {None, "wind"},
            "stop": {None},
            "open": {"door"},
            "touch": {"door", "that"},
        }
        if object_word not in allowed_objects.get(verb_word, set()):
            return None

        object_roots = {
            "door": (self.p["obj"], "zrump", self.p["inan"]),
            "that": (self.p["obj"], "zra", self.p["inan"]),
            "wind": (self.p["goal"], "cuq", self.p["anim"]),
        }
        parts = []
        if object_word:
            case_root, object_root, object_animacy = object_roots[object_word]
            parts.extend([case_root, object_animacy, object_root])
        verb_root = self._known_verb_root(verb_word)
        if not verb_root:
            return None
        parts.extend([self.p["verb"], verb_root, self.p["anim"], self.p["imp"], evidence_root])
        if polite:
            parts.append("naxru")
        if negated:
            parts.append(self.p["neg"])
        return " ".join(parts)

    def _speak_dialogue_frame(self, english: str, evidence_root: str):
        """Handle reviewed dialogue, sound fragments, and commands."""
        clean = re.sub(r"[.!?]+$", "", english.strip().lower())
        clean = re.sub(r"\s+", " ", clean).strip()

        sound_report = re.fullmatch(r"the alarm goes ((?:beep)(?:\s+beep)*)", clean)
        if sound_report:
            sounds = " ".join("nqozo" for _ in sound_report.group(1).split())
            return self._partial_frame(
                f"skump {sounds}",
                "unsupported sound-report frame: goes",
            )

        broken_state = re.fullmatch(r"the (elevator|door) (?:is|are|was|were) broken", clean)
        if broken_state:
            subject_root = {"elevator": "spokta", "door": "zrump"}[broken_state.group(1)]
            return self._partial_frame(subject_root, "unsupported predicate state: broken")

        missing_predicate = re.fullmatch(
            r"(i|you|he|she|we|they) (will|would|can|could|should|may|might|must) not",
            clean,
        )
        if missing_predicate:
            return self._partial_frame("", f"omitted predicate after {clean}")

        imperative = re.fullmatch(
            r"(?:(please)\s+)?(?:(do)\s+(not)\s+)?"
            r"(wait|listen|stop|open|touch)"
            r"(?:\s+(?:to\s+)?(?:the\s+)?(wind|door|that))?"
            r"(?:\s+(please))?",
            clean,
        )
        if imperative:
            polite_before, _do, not_word, verb_word, object_word, polite_after = imperative.groups()
            rendered = self._render_reviewed_imperative(
                verb_word,
                object_word,
                evidence_root=evidence_root,
                negated=bool(not_word),
                polite=bool(polite_before or polite_after),
            )
            if rendered:
                return rendered

        fragment_roots = {
            "ah": "aza", "bang": "tesena", "beep": "nqozo", "drip": "priva",
            "fine": "stux", "huh": "xeha", "no": "nguq", "ouch": "oxu",
            "shhh": "shava", "swish": "zavi", "uh": "ux", "whirr": "glivun",
            "whummmmm": "vrumo", "whoa": "vrifvluq", "whoosh": "qelto",
            "yes": "naxq",
        }
        fragment_words = clean.split()
        if fragment_words and all(word in fragment_roots for word in fragment_words):
            return " ".join(fragment_roots[word] for word in fragment_words)
        return None

    def _speak_guarded_fragment(self, english: str, evidence_root: str):
        """Keep fuzz-discovered subjectless actions readable and honest."""
        clean = re.sub(r"[.!?]+$", "", english.strip().lower())
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            return None

        unsupported_command_verbs = {
            "help", "hide", "reverse", "reverse engineer", "run", "translate",
        }
        subjectless_question = re.fullmatch(r"why\s+(.+)", clean)
        if subjectless_question:
            phrase = subjectless_question.group(1).strip()
            head = "reverse engineer" if phrase.startswith("reverse engineer") else phrase.split(maxsplit=1)[0]
            if head in unsupported_command_verbs:
                return self._partial_frame("", f"unsupported subjectless question: why {phrase}")

        negated = re.fullmatch(r"(?:please\s+)?do not\s+(.+?)(?:\s+please)?", clean)
        if negated:
            phrase = negated.group(1).strip()
            if phrase.split(maxsplit=1)[0] in unsupported_command_verbs or phrase.startswith("reverse engineer"):
                return self._partial_frame("", f"unsupported negated imperative: do not {phrase}")

        command = re.fullmatch(r"(?:please\s+)?(.+?)(?:\s+please)?", clean)
        if command:
            phrase = command.group(1).strip()
            head = "reverse engineer" if phrase.startswith("reverse engineer") else phrase.split(maxsplit=1)[0]
            if head in unsupported_command_verbs:
                return self._partial_frame("", f"unsupported imperative: {phrase}")

        subjectless_actions = {
            "whisper": "whisper",
            "whispers": "whisper",
            "whispered": "whisper",
        }
        if clean in subjectless_actions:
            return self._partial_frame("", f"omitted subject for action: {subjectless_actions[clean]}")
        return None
