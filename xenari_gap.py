#!/usr/bin/env python3
"""Script gap harvesting for Xenari lexicon curation.

This module is deliberately read-only. It extracts missing English words and
phrase candidates from scripts, classifies them into review buckets, and keeps
source context so humans can decide what deserves canon.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Iterable


WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
SPEAKER_RE = re.compile(r"^\s*([A-Z][A-Z0-9 .'\-]{1,40})(?:\:|\s*$)")
TAG_RE = re.compile(r"<[^>]+>")

CONTRACTIONS = {
    "can't": ["can", "not"],
    "cannot": ["can", "not"],
    "won't": ["will", "not"],
    "n't": ["not"],
    "'re": ["are"],
    "'ve": ["have"],
    "'ll": ["will"],
    "'d": ["would"],
    "'m": ["am"],
    "'s": ["is"],
}

VOCALIZATIONS = {
    "ah", "aha", "ahem", "aw", "eh", "er", "ha", "haha", "hehe", "hm", "hmm",
    "hmmm", "huh", "mm", "mmm", "nah", "oh", "ooh", "ow", "ouch", "oof",
    "psst", "sh", "shh", "ssh", "tsk", "uh", "ugh", "um", "umm", "whoa",
    "wow", "yeah", "yep", "yo",
}

SOUND_EFFECTS = {
    "bang", "beep", "boom", "bump", "buzz", "clang", "clank", "click",
    "crack", "crash", "creak", "ding", "drip", "gasp", "groan", "growl",
    "grunt", "gulp", "hiss", "howl", "knock", "moan", "murmur", "pop",
    "ring", "roar", "rumble", "scream", "screech", "shatter", "sigh",
    "slam", "slap", "snap", "snarl", "sniff", "sob", "splash", "squelch",
    "thud", "thump", "tick", "whimper", "whine", "whirr", "whisper",
    "whoosh", "zap",
}

NOISE_WORDS = {
    "align", "center", "font", "href", "http", "https", "nbsp", "sceneheading",
    "stylesheet", "www",
}


@dataclass
class GapOccurrence:
    source: str
    line: int
    raw: str
    context: str
    speaker: str | None = None
    stage_direction: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = {
            "source": self.source,
            "line": self.line,
            "raw": self.raw,
            "context": self.context,
        }
        if self.speaker:
            data["speaker"] = self.speaker
        if self.stage_direction:
            data["stage_direction"] = True
        return data


@dataclass
class GapEntry:
    key: str
    count: int = 0
    forms: Counter = field(default_factory=Counter)
    sources: Counter = field(default_factory=Counter)
    occurrences: list[GapOccurrence] = field(default_factory=list)
    notes: set[str] = field(default_factory=set)
    variant_of: str | None = None

    def add(self, occurrence: GapOccurrence, limit_contexts: int) -> None:
        self.count += 1
        self.forms[occurrence.raw] += 1
        self.sources[occurrence.source] += 1
        if len(self.occurrences) < limit_contexts:
            self.occurrences.append(occurrence)

    def as_dict(self) -> dict[str, Any]:
        data = {
            "key": self.key,
            "count": self.count,
            "forms": dict(self.forms.most_common()),
            "sources": dict(self.sources.most_common()),
            "contexts": [occ.as_dict() for occ in self.occurrences],
        }
        if self.notes:
            data["notes"] = sorted(self.notes)
        if self.variant_of:
            data["variant_of"] = self.variant_of
        return data


@dataclass
class Token:
    raw: str
    norm: str
    source: str
    line: int
    context: str
    speaker: str | None
    stage_direction: bool
    token_index: int
    sentence_index: int

    def occurrence(self) -> GapOccurrence:
        return GapOccurrence(
            source=self.source,
            line=self.line,
            raw=self.raw,
            context=self.context,
            speaker=self.speaker,
            stage_direction=self.stage_direction,
        )


class GapHarvester:
    """Collect every missing script word, then classify it for curation."""

    bucket_order = [
        "lexical_gaps",
        "phrase_gaps",
        "sound_effects",
        "vocalizations",
        "names_places",
        "inflection_variants",
        "covered_by_grammar",
        "extraction_noise",
    ]

    bucket_titles = {
        "lexical_gaps": "Lexical Gaps",
        "phrase_gaps": "Phrase Gaps",
        "sound_effects": "Sound Effects",
        "vocalizations": "Vocalizations",
        "names_places": "Names And Places",
        "inflection_variants": "Inflection Variants",
        "covered_by_grammar": "Covered By Grammar",
        "extraction_noise": "Extraction Noise",
    }

    def __init__(self, xenari: Any, context_limit: int = 3):
        self.xenari = xenari
        self.context_limit = context_limit
        self.known_terms = self._build_known_terms()

    def harvest_paths(
        self,
        paths: Iterable[Path],
        *,
        phrase_min_count: int = 2,
        max_phrase_words: int = 5,
    ) -> dict[str, Any]:
        documents = []
        for path in paths:
            path = Path(path)
            documents.append({
                "source": str(path),
                "text": path.read_text(encoding="utf-8", errors="replace"),
            })
        return self.harvest_documents(
            documents,
            phrase_min_count=phrase_min_count,
            max_phrase_words=max_phrase_words,
        )

    def harvest_documents(
        self,
        documents: Iterable[dict[str, str]],
        *,
        phrase_min_count: int = 2,
        max_phrase_words: int = 5,
    ) -> dict[str, Any]:
        documents = list(documents)
        tokens = []
        for document in documents:
            source = document["source"]
            tokens.extend(self._tokens_for_text(source, document["text"]))

        buckets: dict[str, dict[str, GapEntry]] = {
            name: {} for name in self.bucket_order if name != "phrase_gaps"
        }
        known_count = 0
        for token in tokens:
            bucket, note, variant_of = self._classify_token(token)
            if bucket == "known":
                known_count += 1
                continue
            entry = buckets[bucket].setdefault(token.norm, GapEntry(token.norm))
            entry.variant_of = entry.variant_of or variant_of
            if note:
                entry.notes.add(note)
            entry.add(token.occurrence(), self.context_limit)

        phrase_entries = self._phrase_gaps(tokens, phrase_min_count, max_phrase_words)
        report = {
            "summary": {
                "documents": len(documents),
                "tokens": len(tokens),
                "known_tokens": known_count,
                "unknown_tokens": sum(entry.count for bucket in buckets.values() for entry in bucket.values()),
                "unique_unknown_items": sum(len(bucket) for bucket in buckets.values()),
                "phrase_candidates": len(phrase_entries),
                "phrase_min_count": phrase_min_count,
                "max_phrase_words": max_phrase_words,
            },
            "buckets": {
                name: [entry.as_dict() for entry in self._sorted_entries(bucket.values())]
                for name, bucket in buckets.items()
            },
        }
        report["buckets"]["phrase_gaps"] = [entry.as_dict() for entry in phrase_entries]
        return report

    def render_markdown(self, report: dict[str, Any], *, limit: int = 40) -> str:
        summary = report["summary"]
        lines = [
            "# Xenari Gap Harvest Report",
            "",
            "Mode: read-only; no database writes.",
            "",
            "## Summary",
            "",
            f"- Documents: {summary['documents']}",
            f"- Tokens scanned: {summary['tokens']}",
            f"- Known tokens: {summary['known_tokens']}",
            f"- Unknown tokens captured: {summary['unknown_tokens']}",
            f"- Unique unknown items: {summary['unique_unknown_items']}",
            f"- Phrase candidates: {summary['phrase_candidates']}",
            f"- Phrase settings: min_count={summary['phrase_min_count']}, max_words={summary['max_phrase_words']}",
            "",
        ]
        buckets = report["buckets"]
        for bucket_name in self.bucket_order:
            entries = buckets.get(bucket_name, [])
            title = self.bucket_titles[bucket_name]
            lines.extend([f"## {title}", ""])
            if not entries:
                lines.extend(["No candidates.", ""])
                continue
            shown = entries if limit == 0 else entries[:limit]
            for item in shown:
                forms = ", ".join(f"{form} x{count}" for form, count in list(item["forms"].items())[:4])
                note_bits = []
                if item.get("variant_of"):
                    note_bits.append(f"variant of `{item['variant_of']}`")
                note_bits.extend(item.get("notes", []))
                notes = f" ({'; '.join(note_bits)})" if note_bits else ""
                lines.append(f"- `{item['key']}` x{item['count']}{notes}")
                if forms and forms != item["key"]:
                    lines.append(f"  forms: {forms}")
                for context in item["contexts"][: self.context_limit]:
                    speaker = f" [{context['speaker']}]" if context.get("speaker") else ""
                    lines.append(f"  - {context['source']}:{context['line']}{speaker} - {context['context']}")
            if limit and len(entries) > limit:
                lines.append(f"... {len(entries) - limit} more")
            lines.append("")
        lines.extend([
            "## Suggested Follow-up",
            "",
            "- Review `sound_effects` and `vocalizations` as real lexical candidates, not junk.",
            "- Use `phrase_gaps` for idioms, repeated commands, fixed expressions, and title-like chunks.",
            "- Coin from `lexical_gaps` only after checking `near` and `propose-root`.",
            "- Treat `names_places` as canon candidates only when the name/place matters in-world.",
            "- Treat `extraction_noise` as parser cleanup targets, not vocabulary by default.",
        ])
        return "\n".join(lines) + "\n"

    def render_json(self, report: dict[str, Any]) -> str:
        return json.dumps(report, indent=2, ensure_ascii=False) + "\n"

    def _tokens_for_text(self, source: str, text: str) -> list[Token]:
        tokens = []
        token_index = 0
        sentence_index = 0
        current_speaker = None
        for line_no, raw_line in enumerate(text.splitlines(), 1):
            line = TAG_RE.sub(" ", raw_line).replace("\u2019", "'").replace("\u2018", "'")
            stripped = line.strip()
            if not stripped:
                current_speaker = None
                continue
            speaker = self._speaker_label(stripped)
            if speaker:
                current_speaker = speaker
                continue
            stage = self._is_stage_direction(stripped)
            context = " ".join(stripped.split())
            for match in WORD_RE.finditer(stripped):
                raw = match.group(0)
                for norm in self._normalize_word(raw):
                    if not norm:
                        continue
                    tokens.append(Token(
                        raw=raw,
                        norm=norm,
                        source=source,
                        line=line_no,
                        context=context,
                        speaker=current_speaker,
                        stage_direction=stage,
                        token_index=token_index,
                        sentence_index=sentence_index,
                    ))
                    token_index += 1
            if re.search(r"[.!?]\s*$", stripped):
                sentence_index += 1
        return tokens

    def _speaker_label(self, line: str) -> str | None:
        if len(line) > 48:
            return None
        match = SPEAKER_RE.match(line)
        if not match:
            return None
        label = match.group(1).strip(" :-")
        if not label or any(ch.islower() for ch in label):
            return None
        return label.title()

    def _is_stage_direction(self, line: str) -> bool:
        if line.startswith(("(", "[", "*")) and line.endswith((")", "]", "*")):
            return True
        upper = line.upper()
        return upper.startswith(("INT.", "EXT.", "CUT TO", "FADE IN", "FADE OUT"))

    def _normalize_word(self, raw: str) -> list[str]:
        word = raw.lower().strip("'-.")
        if not word:
            return []
        for suffix, replacement in CONTRACTIONS.items():
            if word.endswith(suffix) and word != suffix:
                stem = word[: -len(suffix)]
                return [stem] + replacement
        return [word]

    def _classify_token(self, token: Token) -> tuple[str, str | None, str | None]:
        word = token.norm
        if self._known(word):
            return "known", None, None
        variant_of = self._known_variant_base(word)
        if variant_of:
            return "inflection_variants", "base form is already known", variant_of
        if self._is_extraction_noise(word):
            return "extraction_noise", "markup/code-looking token", None
        if word in SOUND_EFFECTS or self._sound_effect_shape(word, token):
            return "sound_effects", "sound or embodied action candidate", None
        if word in VOCALIZATIONS or self._vocalization_shape(word):
            return "vocalizations", "interjection/vocal sound candidate", None
        if self._covered_by_grammar(word):
            return "covered_by_grammar", "handled by grammar/pronoun/particle layer", None
        if self._looks_like_name(token):
            return "names_places", "capitalized script token", None
        return "lexical_gaps", None, None

    def _known(self, word: str) -> bool:
        return word.lower().strip() in self.known_terms

    def _build_known_terms(self) -> set[str]:
        known = set(self.xenari.english_to_root)
        known.update(self.xenari.lexicon)
        known.update(self.xenari.en_pronouns)
        for meaning in self.xenari.lexicon.values():
            known.update(self.xenari._meaning_keys(meaning))
        return {item for item in known if item}

    def _known_variant_base(self, word: str) -> str | None:
        candidates = set()
        if word.endswith("ies") and len(word) > 4:
            candidates.add(word[:-3] + "y")
        for suffix in ("ingly", "edly", "ing", "ed", "es", "s", "er", "est", "ly"):
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                candidates.add(word[: -len(suffix)])
        doubled = re.sub(r"([a-z])\1$", r"\1", word[:-3]) if word.endswith("ing") else None
        if doubled:
            candidates.add(doubled)
        for candidate in candidates:
            if self._known(candidate):
                return candidate
        return None

    def _covered_by_grammar(self, word: str) -> bool:
        return (
            word in self.xenari.skip_words
            or word in self.xenari.en_pronouns
            or word in self.xenari.tense_map
            or word in self.xenari.evidential_map
            or word in self.xenari.copula_words
        )

    def _looks_like_name(self, token: Token) -> bool:
        raw = token.raw.strip("'-.")
        if not raw or raw.lower() == raw:
            return False
        if token.stage_direction and raw.isupper() and token.norm in SOUND_EFFECTS:
            return False
        if raw.isupper() and len(raw) <= 4:
            return False
        return True

    def _is_extraction_noise(self, word: str) -> bool:
        if word in NOISE_WORDS:
            return True
        if len(word) > 32:
            return True
        return bool(re.search(r"(.)\1{5,}", word))

    def _sound_effect_shape(self, word: str, token: Token) -> bool:
        if token.stage_direction and len(word) >= 3 and re.fullmatch(r"[a-z]+", word):
            return word in SOUND_EFFECTS or re.search(r"(ck|ng|sh|th|mp|nt|zz|rr|oo)", word) is not None
        return False

    def _vocalization_shape(self, word: str) -> bool:
        if len(word) < 2 or len(word) > 12:
            return False
        if re.fullmatch(r"(ha)+h?", word):
            return True
        return bool(re.fullmatch(r"[aeiouhmnrsw]+", word) and re.search(r"(.)\1", word))

    def _phrase_gaps(
        self,
        tokens: list[Token],
        phrase_min_count: int,
        max_phrase_words: int,
    ) -> list[GapEntry]:
        phrases: dict[str, GapEntry] = {}
        by_sentence: dict[tuple[str, int], list[Token]] = defaultdict(list)
        for token in tokens:
            if self._classify_token(token)[0] in {"extraction_noise", "names_places"}:
                continue
            by_sentence[(token.source, token.sentence_index)].append(token)

        for sentence_tokens in by_sentence.values():
            for start in range(len(sentence_tokens)):
                for size in range(2, max_phrase_words + 1):
                    window = sentence_tokens[start:start + size]
                    if len(window) != size:
                        continue
                    words = [token.norm for token in window]
                    if all(self._known(word) or self._covered_by_grammar(word) for word in words):
                        continue
                    phrase = " ".join(words)
                    if self._known(phrase):
                        continue
                    entry = phrases.setdefault(phrase, GapEntry(phrase))
                    entry.add(GapOccurrence(
                        source=window[0].source,
                        line=window[0].line,
                        raw=" ".join(token.raw for token in window),
                        context=window[0].context,
                        speaker=window[0].speaker,
                        stage_direction=any(token.stage_direction for token in window),
                    ), self.context_limit)

        filtered = [
            entry for entry in phrases.values()
            if entry.count >= phrase_min_count or phrase_min_count <= 1
        ]
        return self._sorted_entries(filtered)

    def _sorted_entries(self, entries: Iterable[GapEntry]) -> list[GapEntry]:
        return sorted(entries, key=lambda item: (-item.count, item.key.count(" "), item.key))
