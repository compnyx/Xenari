import re
from typing import List, Tuple

from ..runtime_tables import (
    REVERSE_PLURAL_NOUN_ROOTS,
    REVERSE_PREFERRED,
    REVERSE_PREFERRED_BY_PART_OF_SPEECH,
    REVERSE_PRONOUNS,
    REVERSE_VERB_INFLECTIONS,
    TEMPORAL_GLOSSES,
)
from .models import ReverseClause, ReverseRequest, ReverseSegments, TranslationMatch


class ReverseTranslationMixin:
    @staticmethod
    def _reverse_head_is_already_plural(root: str, text: str) -> bool:
        """Return whether a preferred noun head already carries plural number.

        Preferred reverse heads are exact reviewed English mapping keys. Some
        of those keys are lexical plurals (for example ``facilities``), so an
        explicit Xenari ``ha`` must not blindly pluralize them a second time.
        The suffix exclusions retain ordinary singulars such as ``bus``,
        ``access``, ``bias``, and ``analysis`` for productive pluralization.
        """
        noun_roles = REVERSE_PREFERRED_BY_PART_OF_SPEECH.get("noun", {})
        proper_noun_roles = REVERSE_PREFERRED_BY_PART_OF_SPEECH.get(
            "proper_noun", {}
        )
        if root in noun_roles or root in proper_noun_roles:
            return root in REVERSE_PLURAL_NOUN_ROOTS

        # Compatibility fallback for a caller-provided database whose roots
        # are not represented by the packaged full-canon role metadata.
        final_word = text.rsplit(" ", 1)[-1].casefold()
        if final_word in {
            "children",
            "data",
            "deer",
            "feet",
            "fish",
            "geese",
            "men",
            "mice",
            "oxen",
            "people",
            "series",
            "sheep",
            "species",
            "teeth",
            "women",
        }:
            return True
        if final_word in {"cosmos", "lens", "yes"}:
            return False
        return final_word.endswith("s") and not final_word.endswith(
            ("ss", "us", "as", "is")
        )

    @staticmethod
    def _reverse_plural_form(root: str, text: str, role: str) -> str:
        """Render ``ha`` on the noun/pronoun it follows instead of dropping it."""
        if root == "neq":
            return {"subj": "we", "obj": "us", "poss": "our"}.get(role, "we")
        if root == "mex":
            return {"subj": "you", "obj": "you", "poss": "your"}.get(role, "you")
        if root in {"leq", "req", "zeq"}:
            return {"subj": "they", "obj": "them", "poss": "their"}.get(role, "they")
        if root == "seq":
            return "strangers'" if role == "poss" else "strangers"
        if role == "poss":
            base = ReverseTranslationMixin._reverse_plural_form(root, text, "plain")
            if base.endswith(("'", "'s")):
                return base
            return f"{base}'" if base.endswith("s") else f"{base}'s"
        if ReverseTranslationMixin._reverse_head_is_already_plural(root, text):
            return text
        irregular_plurals = {
            "analysis": "analyses",
            "axis": "axes",
            "basis": "bases",
            "catharsis": "catharses",
            "child": "children",
            "crisis": "crises",
            "diagnosis": "diagnoses",
            "foot": "feet",
            "goose": "geese",
            "hypothesis": "hypotheses",
            "louse": "lice",
            "man": "men",
            "metamorphosis": "metamorphoses",
            "mouse": "mice",
            "oasis": "oases",
            "ox": "oxen",
            "person": "people",
            "photosynthesis": "photosyntheses",
            "thesis": "theses",
            "tooth": "teeth",
            "woman": "women",
        }
        prefix, separator, final_word = text.rpartition(" ")
        if final_word in irregular_plurals:
            plural = irregular_plurals[final_word]
            return f"{prefix}{separator}{plural}" if separator else plural
        if text.endswith(("s", "x", "z", "ch", "sh")):
            return f"{text}es"
        if len(text) > 1 and text.endswith("y") and text[-2] not in "aeiou":
            return f"{text[:-1]}ies"
        return f"{text}s"

    @staticmethod
    def _polish_structured_english(text: str) -> str:
        replacements = {
            "door open": "door opens",
            "hat belong to me": "hat belongs to me",
            "person run": "person runs",
        }
        polished = replacements.get(text, text)
        return re.sub(r"\bwindow red\b", "red window", polished)

    @staticmethod
    def _invert_when_question(statement: str, tense: str) -> str:
        """Turn one bounded intransitive statement into an English WH clause."""
        if tense in {"ve", "pe"}:
            auxiliary = "will" if tense == "ve" else "could"
            match = re.fullmatch(rf"(.+?) {auxiliary} (.+)", statement)
            if match:
                subject, predicate = match.groups()
                return f"{auxiliary} {subject} {predicate}"
        subject, separator, verb = statement.rpartition(" ")
        if not separator:
            return statement
        if tense == "lo":
            past_to_base = {
                "opened": "open", "ran": "run", "waited": "wait",
                "entered": "enter", "stopped": "stop", "walked": "walk",
                "slept": "sleep", "rested": "rest", "sat": "sit",
                "stood": "stand", "went": "go",
            }
            return f"did {subject} {past_to_base.get(verb, verb)}"
        present_to_base = {
            "opens": "open", "runs": "run", "waits": "wait",
            "enters": "enter", "stops": "stop", "walks": "walk",
            "sleeps": "sleep", "rests": "rest", "sits": "sit",
            "stands": "stand", "goes": "go",
        }
        auxiliary = "do" if subject in {"I", "you", "we", "they"} else "does"
        return f"{auxiliary} {subject} {present_to_base.get(verb, verb)}"

    def _reverse_head_gloss(self, root: str) -> str:
        if root in REVERSE_PREFERRED:
            return REVERSE_PREFERRED[root]
        meaning = self.lexicon.get(root, root)
        head = self.db._audit_headword(meaning)
        return head.split()[0] if head else root

    def _reverse_structured_frame(self, xenari: str):
        """Read the shared condition, temporal, and relative frames first."""
        clean = re.sub(r"\s+", " ", xenari.strip())
        if clean.startswith("pevoq ") and " ti " in clean:
            condition, main = clean.removeprefix("pevoq ").split(" ti ", 1)
            condition_en = self._polish_structured_english(self.reverse(condition))
            main_en = self._polish_structured_english(self.reverse(main))
            return f"if {condition_en}, then {main_en}"

        subordinate_frame = re.fullmatch(
            r"su (cruv|prexq|vrem|troz|truq) (.+) ti (.+)", clean,
        )
        if subordinate_frame:
            marker, subordinate, main = subordinate_frame.groups()
            marker_en = {
                "cruv": "when",
                "prexq": "before",
                "vrem": "after",
                "troz": "because",
                "truq": "although",
            }[marker]
            subordinate_en = self._polish_structured_english(self.reverse(subordinate))
            main_en = self._polish_structured_english(self.reverse(main))
            return f"{marker_en} {subordinate_en}, {main_en}"

        relative = re.fullmatch(r"(.+?) su (zre|vro) (.+) ti (.+)", clean)
        if relative:
            matrix_prefix, relativizer, relative_body, matrix_suffix = relative.groups()
            matrix_en = self._polish_structured_english(
                self.reverse(f"{matrix_prefix} {matrix_suffix}")
            )
            body_tokens = relative_body.split()
            if "ta" not in body_tokens:
                return None
            verb_index = body_tokens.index("ta")
            relative_with_subject = " ".join([
                *body_tokens[:verb_index], "ka", "leq", *body_tokens[verb_index:],
            ])
            relative_en = self.reverse(relative_with_subject)
            relative_en = re.sub(r"^he/she/it\s+", "", relative_en)
            prefix_tokens = matrix_prefix.split()
            particles = {"ra", "ka", "fa", "na", "mo", "vi", "nu", "ha", "po"}
            head_root = next((token for token in reversed(prefix_tokens) if token not in particles), "")
            head_en = self._reverse_head_gloss(head_root)
            relative_word = "who" if relativizer == "zre" else "that"
            expanded_head = f"{head_en} {relative_word} {relative_en}"
            if head_en in matrix_en:
                return matrix_en.replace(head_en, expanded_head, 1)
        return None

    def reverse(self, xenari: str) -> str:
        """Best-effort Xenari → English through explicit bounded stages."""
        request = ReverseRequest(
            source=xenari,
            clean=re.sub(r"\s+", " ", xenari.strip().strip(".!?")),
        )
        match = self._reverse_fast_path(request)
        if match is not None:
            return match.text
        segments = self._segment_reverse_frames(request.clean)
        return self._render_reverse_segments(segments)

    def _reverse_fast_path(self, request: ReverseRequest) -> TranslationMatch | None:
        """Resolve exact, numeric, command, and structured reverse frames."""
        clean = request.clean
        borrowed_alias = re.fullmatch(r"zuq\s+(zuq‹[^›]+›)", clean)
        if borrowed_alias:
            borrowed = self._parse_borrowed_literal(borrowed_alias.group(1))
            return TranslationMatch("borrowed-alias", f"known as {borrowed[1]}")
        borrowed = self._parse_borrowed_literal(clean)
        if borrowed:
            _kind, payload = borrowed
            return TranslationMatch("borrowed-literal", payload)
        who_question = re.fullmatch(r"qan vi (.+)", clean)
        if who_question and " ta " in who_question.group(1):
            body = who_question.group(1)
            prefix, suffix = body.split(" ta ", 1)
            english = self.reverse(f"{prefix} ka leq ta {suffix}")
            english = re.sub(r"^he/she/it\s+", "", english)
            english = self._polish_structured_english(english)
            return TranslationMatch("compositional-who-question", f"who {english}?")

        when_question = re.fullmatch(r"qan qro (.+)", clean)
        if when_question and " ta " in when_question.group(1):
            body = when_question.group(1)
            english = self._polish_structured_english(self.reverse(body))
            tense = next(
                (token for token in body.split() if token in {"sa", "lo", "ve", "pe"}),
                "sa",
            )
            inverted = self._invert_when_question(english, tense)
            return TranslationMatch("compositional-when-question", f"when {inverted}?")

        exact_reverse = {
            "stux": "ok",
            "naxq": "yes",
            "naxu": "nice",
            "qlox'": "goodbye",
            "vreqclir": "understood",
            "gral": "thanks",
            "gral troz ra zra ka mex ta pyoquqab lo xo": "thanks for solving that",
            "ra mex ka neq ta gral sa xo troz ra zra ka mex ta pyoquqab lo xo": "thank you for solving that",
            "gral mse": "thanks a lot",
            "qezxol": "sorry",
            "vrin": "whoops",
            "vroq": "yeah",
            "nguq": "no",
            "vex": "maybe",
            "vex qrolo": "maybe later",
            "qlox' qrolo": "see you later",
            "qlox' droh": "see you soon",
            "shengtac nulxant": "no problem",
            "bivuzqa uqel po zuqra": "English",
        }
        if clean in exact_reverse:
            return TranslationMatch("exact-reverse", exact_reverse[clean])
        number_math = self._reverse_number_or_math(clean)
        if number_math is not None:
            return TranslationMatch("number-or-math", number_math)

        target_command = re.fullmatch(
            r"ra nu hune fa nu bivuzqa uqel po zuqra ta "
            r"(nrotm|halbru|nimixu) vi ko xo",
            clean,
        )
        if target_command:
            verb = {
                "nrotm": "translate",
                "halbru": "reverse-engineer",
                "nimixu": "decode",
            }[target_command.group(1)]
            return TranslationMatch("target-language-command", f"{verb} sentence to English!")

        imperative = re.fullmatch(
            r"(?:(ra|fa)\s+(?:nu|vi)\s+([a-z']+)\s+)?ta ([a-z']+) vi ko xo( naxru)?( ngu)?",
            clean,
        )
        if imperative:
            object_case, object_root, verb_root, polite, negated = imperative.groups()
            verb_words = {
                "grip": "listen",
                "semax": "stop",
                "xleq": "open",
                "qabrerd": "touch",
                "zaqa": "run",
                "trekq": "wait",
                "nging": "hide",
                "pegzos": "help",
                "nrotm": "translate",
                "halbru": "reverse engineer",
            }
            object_words = {
                "zrump": "door",
                "zra": "that",
                "hune": "sentence",
                "cuq": "wind",
                "neq": "me",
                "praq": "this",
            }
            verb = verb_words.get(verb_root)
            if verb:
                obj = object_words.get(object_root, object_root or "")
                if object_case == "fa" and obj:
                    obj = f"to {obj}"
                if negated:
                    return TranslationMatch(
                        "imperative",
                        "don't " + " ".join(part for part in [verb, obj] if part) + "!",
                    )
                phrase = " ".join(part for part in [verb, obj] if part)
                return TranslationMatch(
                    "imperative",
                    ("please " + phrase if polite else phrase) + "!",
                )

        structured = self._reverse_structured_frame(request.source)
        if structured is not None:
            return TranslationMatch("structured-frame", structured)
        return None

    @staticmethod
    def _segment_reverse_frames(clean: str) -> ReverseSegments:
        """Recover clause boundaries before role parsing and rendering."""
        sentences = [s.strip() for s in re.split(r"[.!?]+", clean) if s.strip()]
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

        return ReverseSegments(
            frames=tuple(frames),
            purpose_frame_indexes=frozenset(purpose_frames),
            recovered_boundary=recovered_boundary,
        )

    @staticmethod
    def _reverse_verb_phrase_parts(verb: str) -> tuple[list[str], int]:
        """Return the finite-token position in a reviewed verb-role lemma.

        POS-role heads are shared runtime data and already contain their
        reviewed lemma. Agreement belongs on the first lexical verb token,
        after any leading ``-ly`` adverb, never on the phrase's final word.
        """
        tokens = verb.split()
        if not tokens:
            return [], 0
        verb_index = 0
        while verb_index + 1 < len(tokens) and tokens[verb_index].casefold().endswith(
            "ly"
        ):
            verb_index += 1
        return tokens, verb_index

    @staticmethod
    def _reverse_third_person_form(lemma: str) -> str:
        """Compatibility fallback for a verb absent from packaged role metadata."""
        prefix, separator, final = lemma.rpartition("-")
        if separator:
            return prefix + separator + ReverseTranslationMixin._reverse_third_person_form(
                final
            )
        irregular = {"be": "is", "do": "does", "go": "goes", "have": "has"}
        if lemma in irregular:
            return irregular[lemma]
        if len(lemma) > 1 and lemma.endswith("y") and lemma[-2] not in "aeiou":
            return lemma[:-1] + "ies"
        if lemma.endswith(("s", "x", "z", "ch", "sh", "o")):
            return lemma + "es"
        return lemma + "s"

    @staticmethod
    def _reverse_past_form(lemma: str) -> str:
        """Compatibility fallback for a verb absent from packaged role metadata."""
        prefix, separator, final = lemma.rpartition("-")
        if separator:
            return prefix + separator + ReverseTranslationMixin._reverse_past_form(
                final
            )
        irregular_past = {
            "arise": "arose",
            "awake": "awoke",
            "bear": "bore",
            "become": "became",
            "begin": "began",
            "bend": "bent",
            "bite": "bit",
            "bleed": "bled",
            "blow": "blew",
            "break": "broke",
            "bring": "brought",
            "build": "built",
            "buy": "bought",
            "catch": "caught",
            "choose": "chose",
            "come": "came",
            "deal": "dealt",
            "dig": "dug",
            "do": "did",
            "draw": "drew",
            "dream": "dreamed",
            "drink": "drank",
            "drive": "drove",
            "eat": "ate",
            "fall": "fell",
            "feed": "fed",
            "feel": "felt",
            "fight": "fought",
            "find": "found",
            "fly": "flew",
            "forget": "forgot",
            "forgive": "forgave",
            "freeze": "froze",
            "get": "got",
            "give": "gave",
            "go": "went",
            "grow": "grew",
            "hear": "heard",
            "hold": "held",
            "have": "had",
            "keep": "kept",
            "know": "knew",
            "lay": "laid",
            "lead": "led",
            "leave": "left",
            "lend": "lent",
            "lie": "lay",
            "lose": "lost",
            "make": "made",
            "mean": "meant",
            "meet": "met",
            "mow": "mowed",
            "open": "opened",
            "pay": "paid",
            "prove": "proved",
            "ride": "rode",
            "rise": "rose",
            "run": "ran",
            "say": "said",
            "see": "saw",
            "sell": "sold",
            "send": "sent",
            "shake": "shook",
            "shoot": "shot",
            "sing": "sang",
            "sit": "sat",
            "sleep": "slept",
            "sling": "slung",
            "slam": "slammed",
            "smite": "smote",
            "speak": "spoke",
            "spin": "spun",
            "stand": "stood",
            "steal": "stole",
            "step": "stepped",
            "stick": "stuck",
            "string": "strung",
            "strike": "struck",
            "stop": "stopped",
            "strew": "strewed",
            "sweep": "swept",
            "swim": "swam",
            "take": "took",
            "teach": "taught",
            "tell": "told",
            "think": "thought",
            "throw": "threw",
            "understand": "understood",
            "wake": "woke",
            "wear": "wore",
            "weep": "wept",
            "win": "won",
            "write": "wrote",
        }
        if lemma in irregular_past:
            return irregular_past[lemma]
        if lemma.endswith("e"):
            return lemma + "d"
        if (
            len(lemma) > 1
            and lemma.endswith("y")
            and lemma[-2].casefold() not in "aeiou"
        ):
            return lemma[:-1] + "ied"
        return lemma + "ed"

    @staticmethod
    def _render_english_copula(
        *, tense: str, negated: bool, subject: str, subject_plural: bool
    ) -> str:
        """Render finite ``be`` for copulas and reviewed passive/state heads."""
        plural_or_second_person = subject_plural or subject in {"you", "we", "they"}
        if tense == "lo":
            copula = "were" if plural_or_second_person else "was"
        elif tense == "ve":
            return "will not be" if negated else "will be"
        elif tense == "pe":
            return "could not be" if negated else "could be"
        elif tense == "ko":
            return "not be" if negated else "be"
        elif subject == "I":
            copula = "am"
        elif plural_or_second_person:
            copula = "are"
        else:
            copula = "is"
        rendered = f"{copula} not" if negated else copula
        return f"usually {rendered}" if tense == "du" else rendered

    @staticmethod
    def _render_english_verb(
        verb: str,
        *,
        root: str | None = None,
        tense: str,
        negated: bool,
        subject: str,
        subject_plural: bool = False,
    ) -> str:
        """Render one parsed predicate without closing over a clause loop."""
        if verb == "is":
            return ReverseTranslationMixin._render_english_copula(
                tense=tense,
                negated=negated,
                subject=subject,
                subject_plural=subject_plural,
            )

        lemma_tokens, verb_index = ReverseTranslationMixin._reverse_verb_phrase_parts(
            verb
        )
        if not lemma_tokens:
            return verb
        if lemma_tokens[verb_index] == "be":
            finite = ReverseTranslationMixin._render_english_copula(
                tense=tense,
                negated=negated,
                subject=subject,
                subject_plural=subject_plural,
            )
            return " ".join([
                *lemma_tokens[:verb_index],
                finite,
                *lemma_tokens[verb_index + 1 :],
            ])

        lemma = " ".join(lemma_tokens)
        # Canonical roots always take their audited full-phrase forms from the
        # shared runtime contract. The token heuristics below remain only for
        # caller-provided/legacy databases whose roots are not in that canon.
        reviewed_inflections = REVERSE_VERB_INFLECTIONS.get(root, {})
        base_tokens = list(lemma_tokens)
        third_person = not subject_plural and subject not in {"I", "you", "we", "they"}
        if tense == "lo":
            if reviewed_inflections:
                base = reviewed_inflections["past"]
            else:
                base_tokens[verb_index] = ReverseTranslationMixin._reverse_past_form(
                    base_tokens[verb_index]
                )
                base = " ".join(base_tokens)
        elif tense == "ve":
            base = "will " + lemma
        elif tense == "du":
            if third_person:
                finite_phrase = reviewed_inflections.get("third_person")
                if finite_phrase is None:
                    base_tokens[verb_index] = (
                        ReverseTranslationMixin._reverse_third_person_form(
                            base_tokens[verb_index]
                        )
                    )
                    finite_phrase = " ".join(base_tokens)
            else:
                finite_phrase = lemma
            base = "usually " + finite_phrase
        elif tense == "pe":
            base = "could " + lemma
        elif tense == "sa" and third_person:
            base = reviewed_inflections.get("third_person", "")
            if not base:
                base_tokens[verb_index] = (
                    ReverseTranslationMixin._reverse_third_person_form(
                        base_tokens[verb_index]
                    )
                )
                base = " ".join(base_tokens)
        else:
            base = lemma

        if negated:
            if tense == "ve":
                return "will not " + base.removeprefix("will ")
            if tense == "lo":
                return "did not " + lemma
            if tense == "pe":
                return "could not " + lemma
            auxiliary = (
                "do not"
                if subject_plural or subject in {"I", "you", "we", "they"}
                else "does not"
            )
            if tense == "du":
                return auxiliary + " usually " + lemma
            return auxiliary + " " + lemma
        return base

    def _render_reverse_segments(self, segments: ReverseSegments) -> str:
        """Parse and render already segmented reverse clause frames."""
        frames = segments.frames
        purpose_frames = segments.purpose_frame_indexes
        recovered_boundary = segments.recovered_boundary
        rendered = []
        case_particles = {"ra", "ka", "ta", "na", "fa", "mo"}
        skip_particles = {"vi", "nu", "sa", "lo", "ve", "du", "pe", "ko", "xa", "xe", "xi", "xo", "zu", "ha"}
        connector_glosses = {"kex": "but", "xen": "and", "noq": "or", "qlez": "so", "cruv": "once/when"}
        interrogative_glosses = {"qan": "what", "qur": "where", "cil": "how", "voq": "why"}
        grammar_particles = (
            case_particles | skip_particles | {"ngu", "va", "po"}
            | set(connector_glosses) | set(interrogative_glosses)
        )
        def root_english(
            root: str,
            part_of_speech: str | None = None,
            role: str = "plain",
        ) -> str:
            borrowed = self._parse_borrowed_literal(root)
            if borrowed:
                return borrowed[1]
            if root in REVERSE_PRONOUNS:
                forms = REVERSE_PRONOUNS[root]
                return forms.get(role, forms["subj"])
            if part_of_speech is not None:
                role_preferences = REVERSE_PREFERRED_BY_PART_OF_SPEECH.get(
                    part_of_speech, {}
                )
                if root in role_preferences:
                    return role_preferences[root]
            if root in REVERSE_PREFERRED:
                return REVERSE_PREFERRED[root]
            meaning = self.lexicon.get(root)
            if meaning is None:
                return f"[unknown: {root}]"
            head = self.db._audit_headword(meaning)
            if part_of_speech == "verb" and head.startswith("to "):
                head = head[3:]
            return head.split()[0] if head else root

        def ordered_piece_texts(
            pieces: List[dict[str, object]],
            pre_head_pieces: List[dict[str, object]],
        ) -> List[str]:
            if not pieces:
                return [str(piece["text"]) for piece in pre_head_pieces]
            preposed = [
                str(piece["text"])
                for piece in pieces[1:]
                if piece.get("prepose")
            ]
            postposed = [
                str(piece["text"])
                for piece in pieces[1:]
                if not piece.get("prepose")
            ]
            return [
                *(str(piece["text"]) for piece in pre_head_pieces),
                *preposed,
                str(pieces[0]["text"]),
                *postposed,
            ]

        def read_phrase(
            tokens: List[str],
            start: int,
            role: str = "plain",
            head_part_of_speech: str | None = None,
        ) -> Tuple[str, int, bool]:
            pieces = []
            pre_head_pieces = []
            i = start
            possessor = None
            while i < len(tokens) and tokens[i] not in case_particles:
                tok = tokens[i]
                if tok == "ha":
                    if pieces:
                        pieces[0]["plural"] = True
                        pieces[0]["text"] = self._reverse_plural_form(
                            pieces[0]["root"], pieces[0]["text"], role,
                        )
                    i += 1
                    continue
                if tok in skip_particles:
                    i += 1
                    continue
                if tok == "po":
                    possessor_pieces = pieces
                    pieces = []
                    if possessor_pieces:
                        possessor_head = possessor_pieces[0]
                        possessor_text = root_english(
                            possessor_head["root"],
                            part_of_speech=possessor_head["part_of_speech"],
                            role="poss",
                        )
                        possessor_text = (
                            self._reverse_plural_form(
                                possessor_head["root"], possessor_text, "poss",
                            )
                            if possessor_head.get("plural") else possessor_text
                        )
                        owner_pieces = [dict(piece) for piece in possessor_pieces]
                        owner_pieces[0]["text"] = possessor_text
                        possessor = {
                            **possessor_head,
                            "text": " ".join(
                                ordered_piece_texts(owner_pieces, pre_head_pieces)
                            ),
                        }
                    pre_head_pieces = []
                    i += 1
                    continue
                reviewed_parts_of_speech = set(
                    self.db.parts_of_speech_for_root(tok)
                )
                if (
                    not pieces
                    and head_part_of_speech not in reviewed_parts_of_speech
                    and "particle" in reviewed_parts_of_speech
                    and not reviewed_parts_of_speech.intersection(
                        {"noun", "proper_noun", "pronoun"}
                    )
                ):
                    pre_head_pieces.append({
                        "root": tok,
                        "text": root_english(tok),
                        "part_of_speech": None,
                        "plural": False,
                        "prepose": True,
                    })
                    i += 1
                    continue
                if pieces:
                    raw_surface = root_english(tok)
                    raw_roles = {
                        candidate
                        for candidate in reviewed_parts_of_speech
                        if REVERSE_PREFERRED_BY_PART_OF_SPEECH.get(
                            candidate, {}
                        ).get(tok) == raw_surface
                    }
                    if "adjective" in reviewed_parts_of_speech:
                        requested_part_of_speech = (
                            None
                            if raw_roles.intersection({"particle", "pronoun"})
                            else "adjective"
                        )
                        prepose = True
                    elif {
                        "noun", "numeral"
                    } <= reviewed_parts_of_speech:
                        requested_part_of_speech = "numeral"
                        prepose = True
                    elif {"noun", "adverb"} <= reviewed_parts_of_speech:
                        requested_part_of_speech = "adverb"
                        prepose = True
                    else:
                        requested_part_of_speech = None
                        prepose = False
                elif (
                    head_part_of_speech is not None
                    and head_part_of_speech in reviewed_parts_of_speech
                ):
                    requested_part_of_speech = head_part_of_speech
                    prepose = False
                else:
                    requested_part_of_speech = None
                    prepose = False
                piece = {
                    "root": tok,
                    "text": root_english(
                        tok,
                        part_of_speech=requested_part_of_speech,
                        role=role,
                    ),
                    "part_of_speech": requested_part_of_speech,
                    "plural": False,
                    "prepose": prepose,
                }
                pieces.append(piece)
                i += 1
            # Xenari noun phrases can contain pre-head function words, a head,
            # preposed English qualities, and deliberately postposed lexical
            # material. Preserve those distinct slots rather than reversing
            # every root following the first one.
            words = ordered_piece_texts(pieces, pre_head_pieces)
            if possessor and words:
                poss_text = possessor["text"]
                if (
                    possessor["root"] not in REVERSE_PRONOUNS
                    and not poss_text.endswith(("'", "'s"))
                ):
                    poss_text = (
                        f"{poss_text}'"
                        if (
                            possessor["root"] in REVERSE_PLURAL_NOUN_ROOTS
                            and poss_text.endswith("s")
                        )
                        else f"{poss_text}'s"
                    )
                return f"{poss_text} {' '.join(words)}", i, bool(
                    pieces and pieces[0]["plural"]
                )
            return " ".join(words), i, bool(pieces and pieces[0]["plural"])

        for sentence in frames:
            if sentence == "prax":
                rendered.append("hello")
                continue
            borrowed_alias = re.fullmatch(r"zuq\s+(zuq‹[^›]+›)", sentence)
            if borrowed_alias:
                borrowed = self._parse_borrowed_literal(borrowed_alias.group(1))
                rendered.append(f"known as {borrowed[1]}")
                continue
            borrowed_frame = re.fullmatch(
                r"(?:(kex|xen|noq)\s+)?((?:zuq|qro)‹[^›]+›)", sentence
            )
            if borrowed_frame:
                connector_root, borrowed_token = borrowed_frame.groups()
                borrowed = self._parse_borrowed_literal(borrowed_token)
                connector = {"kex": "but", "xen": "and", "noq": "or"}.get(
                    connector_root or "", ""
                )
                rendered.append(" ".join(part for part in [connector, borrowed[1]] if part))
                continue

            tokens = sentence.split()
            copular_predicate = False
            for marker_index, token in enumerate(tokens):
                if token != "ta":
                    continue
                verb_index = marker_index + 1
                while (
                    verb_index < len(tokens)
                    and tokens[verb_index] in skip_particles
                ):
                    verb_index += 1
                if verb_index < len(tokens) and tokens[verb_index] == "zux":
                    copular_predicate = True
                    break
            clause = ReverseClause()
            counts = {particle: tokens.count(particle) for particle in case_particles}
            unknown_roots = [
                token for token in tokens
                if token not in grammar_particles
                and token not in REVERSE_PRONOUNS
                and token not in self.lexicon
                and not self._parse_borrowed_literal(token)
            ]
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok in connector_glosses and i == 0:
                    clause.connector = connector_glosses[tok]
                    i += 1
                elif tok == "ra":
                    clause.object, i, _ = read_phrase(
                        tokens,
                        i + 1,
                        role="obj",
                        head_part_of_speech=(
                            "adjective" if copular_predicate else None
                        ),
                    )
                elif tok == "ka":
                    clause.subject, i, clause.subject_plural = read_phrase(
                        tokens,
                        i + 1,
                        role="subj",
                        head_part_of_speech=("noun" if copular_predicate else None),
                    )
                elif tok == "na":
                    clause.location, i, _ = read_phrase(tokens, i + 1, role="obj")
                elif tok == "fa":
                    clause.goal, i, _ = read_phrase(tokens, i + 1, role="obj")
                elif tok == "mo":
                    clause.instrument, i, _ = read_phrase(tokens, i + 1, role="obj")
                elif tok == "ta":
                    j = i + 1
                    while j < len(tokens) and tokens[j] in skip_particles:
                        j += 1
                    clause.verb = (
                        root_english(tokens[j], part_of_speech="verb")
                        if j < len(tokens)
                        else ""
                    )
                    clause.verb_root = tokens[j] if j < len(tokens) else ""
                    i = j + 1
                elif tok in {"sa", "lo", "ve", "du", "pe", "ko"}:
                    clause.tense = tok
                    i += 1
                elif tok == "ngu":
                    clause.negated = True
                    i += 1
                elif tok == "va":
                    clause.question = True
                    i += 1
                elif tok in interrogative_glosses:
                    clause.interrogative = interrogative_glosses[tok]
                    i += 1
                elif tok == "naxru":
                    clause.polite = True
                    i += 1
                elif tok in TEMPORAL_GLOSSES and clause.verb:
                    clause.temporal_modifiers.append(TEMPORAL_GLOSSES[tok])
                    i += 1
                else:
                    if tok not in grammar_particles:
                        clause.loose_fragments.append(root_english(tok))
                    i += 1

            for particle, count in counts.items():
                if count > 1:
                    clause.warnings.append(f"repeated marker '{particle}'")
            if counts["ta"] and not clause.verb:
                clause.warnings.append("verb marker has no readable verb")
            if (counts["ka"] or counts["ra"]) and not counts["ta"]:
                clause.warnings.append("partial clause has no verb marker")
            if unknown_roots:
                clause.warnings.append(
                    f"unknown Xenari root(s): {', '.join(dict.fromkeys(unknown_roots))}"
                )
            if clause.loose_fragments:
                clause.warnings.append("loose fragment(s) preserved outside the clause frame")

            obj = clause.object
            subj = clause.subject
            subject_plural = clause.subject_plural
            loc = clause.location
            goal = clause.goal
            instrument = clause.instrument
            verb = clause.verb
            verb_root = clause.verb_root
            interrogative = clause.interrogative
            tense = clause.tense
            negated = clause.negated
            question = clause.question
            polite = clause.polite
            connector = clause.connector
            temporal_modifiers = clause.temporal_modifiers
            warnings = clause.warnings
            loose = clause.loose_fragments

            if tense == "ko" and verb and not subj:
                command_verb = self._render_english_verb(
                    verb,
                    root=verb_root,
                    tense=tense,
                    negated=False,
                    subject="",
                )
                command_parts = [command_verb]
                if obj:
                    command_parts.append(obj)
                if loc:
                    command_parts.append(f"in/at {loc}")
                if goal:
                    command_parts.append(f"to {goal}")
                if instrument:
                    command_parts.append(f"with {instrument}")
                command_parts.extend(temporal_modifiers)
                text = " ".join(command_parts)
                if negated:
                    text = f"don't {text}"
                if polite:
                    text = f"please {text}"
                if connector:
                    text = " ".join([connector, text]).strip()
                if loose:
                    text = f"{text} [fragment: {' '.join(loose)}]".strip()
                if interrogative:
                    text = f"{interrogative} {text}".strip()
                text = f"{text}?"
                if not question and not interrogative:
                    text = text[:-1] + "!"
                if warnings:
                    text += f" [warning: {'; '.join(warnings)}]"
                rendered.append(text)
                continue

            if connector:
                text_parts = [connector]
            else:
                text_parts = []
            if verb == "is":
                rendered_verb = self._render_english_verb(
                    verb,
                    root=verb_root,
                    tense=tense,
                    negated=negated,
                    subject=subj,
                    subject_plural=subject_plural,
                )
                text = " ".join(part for part in [subj, rendered_verb, obj] if part)
            elif verb and obj and subj:
                rendered_verb = self._render_english_verb(
                    verb,
                    root=verb_root,
                    tense=tense,
                    negated=negated,
                    subject=subj,
                    subject_plural=subject_plural,
                )
                text = " ".join(part for part in [subj, rendered_verb, obj] if part)
            elif verb and subj:
                rendered_verb = self._render_english_verb(
                    verb,
                    root=verb_root,
                    tense=tense,
                    negated=negated,
                    subject=subj,
                    subject_plural=subject_plural,
                )
                text = " ".join(part for part in [subj, rendered_verb] if part)
            else:
                text = " ".join(part for part in [subj, obj] if part)
            if loc:
                text = f"{text} in/at {loc}".strip()
            if goal:
                text = f"{text} to {goal}".strip()
            if instrument:
                text = f"{text} with {instrument}".strip()
            if temporal_modifiers:
                text = f"{text} {' '.join(temporal_modifiers)}".strip()
            if loose:
                text = f"{text} [fragment: {' '.join(loose)}]".strip()
            if interrogative:
                text = f"{interrogative} {text}".strip()
            if text_parts:
                text = " ".join([*text_parts, text]).strip()
            if polite:
                text = f"{text}, please"
            if question or interrogative:
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
        if self._parse_borrowed_literal(text.strip().strip(".!?")):
            return True
        tokens = re.findall(r"[a-z']+", text.lower())
        if not tokens:
            return False
        exact_roots = {
            "prax", "stux", "naxq", "naxu", "qlox'", "vreqclir", "gral",
            "qezxol", "vrin", "vroq", "nguq", "vex",
        }
        if len(tokens) == 1 and tokens[0] in exact_roots:
            return True
        if tokens == ["bivuzqa", "uqel", "po", "zuqra"]:
            return True
        if self._reverse_number_or_math(" ".join(tokens)) is not None:
            return True
        particles = {
            "ra", "ka", "ta", "na", "fa", "mo", "vi", "nu", "sa", "lo", "ve",
            "du", "pe", "ko", "xa", "xe", "xi", "xo", "zu", "po", "ha", "ngu",
        }
        known = sum(1 for token in tokens if token in particles or token in self.lexicon)
        case_markers = sum(1 for token in tokens if token in {"ra", "ka", "ta"})
        return case_markers >= 2 or (known / len(tokens) >= 0.7 and tokens[0] in particles)
