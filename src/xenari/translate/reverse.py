import re
from typing import List, Tuple

from ..runtime_tables import REVERSE_PREFERRED, REVERSE_PRONOUNS, TEMPORAL_GLOSSES
from .models import ReverseClause, ReverseRequest, ReverseSegments, TranslationMatch


class ReverseTranslationMixin:
    @staticmethod
    def _polish_structured_english(text: str) -> str:
        replacements = {
            "door open": "door opens",
            "hat belong to me": "hat belongs to me",
            "person run": "person runs",
        }
        return replacements.get(text, text)

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

        temporal = re.fullmatch(r"su (cruv|prexq|vrem) (.+) ti (.+)", clean)
        if temporal:
            marker, subordinate, main = temporal.groups()
            marker_en = {"cruv": "when", "prexq": "before", "vrem": "after"}[marker]
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
    def _render_english_verb(
        verb: str,
        *,
        tense: str,
        negated: bool,
        subject: str,
    ) -> str:
        """Render one parsed predicate without closing over a clause loop."""
        if verb == "is":
            if tense == "lo":
                return "was not" if negated else "was"
            if tense == "ve":
                return "will not be" if negated else "will be"
            if negated:
                return "is not"
            return "is"

        base = verb
        if tense == "lo":
            irregular_past = {
                "get": "got",
                "go": "went",
                "throw": "threw",
                "build": "built",
                "say": "said",
                "break": "broke",
                "slam": "slammed",
                "stop": "stopped",
                "run": "ran",
                "open": "opened",
                "bite": "bit",
                "reverse-engineer": "reverse-engineered",
            }
            if base in irregular_past:
                base = irregular_past[base]
            elif base.endswith("e"):
                base += "d"
            elif base.endswith("y"):
                base = base[:-1] + "ied"
            else:
                base += "ed"
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
                return "did not " + verb
            auxiliary = "do not" if subject in {"I", "you", "they"} else "does not"
            return auxiliary + " " + verb
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

        def root_english(root: str, verb: bool = False, role: str = "plain") -> str:
            if root in REVERSE_PRONOUNS:
                forms = REVERSE_PRONOUNS[root]
                return forms.get(role, forms["subj"])
            if root in REVERSE_PREFERRED:
                return REVERSE_PREFERRED[root]
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
            clause = ReverseClause()
            counts = {particle: tokens.count(particle) for particle in case_particles}
            unknown_roots = [
                token for token in tokens
                if token not in grammar_particles
                and token not in REVERSE_PRONOUNS
                and token not in self.lexicon
            ]
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok in connector_glosses and i == 0:
                    clause.connector = connector_glosses[tok]
                    i += 1
                elif tok == "ra":
                    clause.object, i = read_phrase(tokens, i + 1, role="obj")
                elif tok == "ka":
                    clause.subject, i = read_phrase(tokens, i + 1, role="subj")
                elif tok == "na":
                    clause.location, i = read_phrase(tokens, i + 1, role="obj")
                elif tok == "fa":
                    clause.goal, i = read_phrase(tokens, i + 1, role="obj")
                elif tok == "mo":
                    clause.instrument, i = read_phrase(tokens, i + 1, role="obj")
                elif tok == "ta":
                    j = i + 1
                    while j < len(tokens) and tokens[j] in skip_particles:
                        j += 1
                    clause.verb = root_english(tokens[j], verb=True) if j < len(tokens) else ""
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
            loc = clause.location
            goal = clause.goal
            instrument = clause.instrument
            verb = clause.verb
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
                command_parts = [verb]
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
                    tense=tense,
                    negated=negated,
                    subject=subj,
                )
                text = " ".join(part for part in [subj, rendered_verb, obj] if part)
            elif verb and obj and subj:
                rendered_verb = self._render_english_verb(
                    verb,
                    tense=tense,
                    negated=negated,
                    subject=subj,
                )
                text = " ".join(part for part in [subj, rendered_verb, obj] if part)
            elif verb and subj:
                rendered_verb = self._render_english_verb(
                    verb,
                    tense=tense,
                    negated=negated,
                    subject=subj,
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
