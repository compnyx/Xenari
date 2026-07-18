"""English normalization and phrase helpers for forward translation."""

import re
from typing import List, Tuple

from ..runtime_tables import ENGLISH_CONTRACTIONS, SENTENCE_FINAL_TEMPORALS


class EnglishPreprocessingMixin:
    """Prepare bounded English clauses and resolve reviewed phrase forms."""

    _sentence_final_temporals = SENTENCE_FINAL_TEMPORALS

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
        apostrophes = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "＇": "'", "`": "'"})
        expanded = text.lower().translate(apostrophes)
        for contraction, replacement in ENGLISH_CONTRACTIONS.items():
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
        curated_pos = self.english_part_of_speech.get(clean)
        if curated_pos is not None:
            return self.english_to_root.get(clean) if curated_pos == "verb" else None
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
            candidate_pos = self.english_part_of_speech.get(candidate)
            if candidate_pos is not None:
                if candidate_pos == "verb":
                    return self.english_to_root.get(candidate)
                continue
            if candidate in self.verb_map:
                return self.verb_map[candidate]
            root, meaning = self.lookup(candidate)
            if root and (meaning or "").lower().startswith("to "):
                return root
        return None

    def _is_verb_like(self, word: str) -> bool:
        """Heuristic: is this word likely a verb?"""
        curated_pos = self.english_part_of_speech.get(word)
        if curated_pos is not None:
            return curated_pos == "verb"
        if word in self.verb_map or word in self.copula_words:
            return True
        _root, meaning = self.lookup(word)
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
