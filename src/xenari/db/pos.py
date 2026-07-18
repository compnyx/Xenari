"""Sense-level part-of-speech metadata and conservative curation support."""

import re
from collections import Counter
from typing import Optional

from ..grammar import DEFAULT_GRAMMAR

PARTS_OF_SPEECH = frozenset(
    {
        "adjective",
        "adverb",
        "ideophone",
        "interjection",
        "noun",
        "numeral",
        "particle",
        "pronoun",
        "proper_noun",
        "verb",
    }
)

POS_SCHEMA_VERSION = "2026-07-18.2"
POS_BACKFILL_VERSION = "2026-07-18.3"

# Particle evidence must be sense-specific.  Several grammar roots are also
# ordinary lexical roots (for example ``xi`` = reported evidential / disturb
# and ``ta`` = verb marker / module), so root membership alone is unsafe.
REVIEWED_PARTICLE_KEYS_BY_ROOT = {
    "cruv": frozenset({"when", "while"}),
    "du": frozenset({"habitual", "tense"}),
    "fa": frozenset({"goal", "marker"}),
    "frex": frozenset({"clause", "marker", "order", "purpose"}),
    "ha": frozenset({"plural"}),
    "ka": frozenset({"marker", "subject"}),
    "kex": frozenset({"but"}),
    "ko": frozenset({"imperative"}),
    "lo": frozenset({"past", "tense"}),
    "mo": frozenset({"instrument", "marker"}),
    "na": frozenset({"location", "marker"}),
    "ngu": frozenset({"negation"}),
    "noq": frozenset({"or"}),
    "nu": frozenset({"inanimate"}),
    "pe": frozenset({"conditional", "potential", "tense"}),
    "pevoq": frozenset({"conditional", "if"}),
    "pli": frozenset({"focus", "particle"}),
    "po": frozenset({"possessive"}),
    "prexq": frozenset({"before"}),
    "qlez": frozenset({"so", "therefore"}),
    "ra": frozenset({"marker", "object"}),
    "sa": frozenset({"ongoing", "present", "tense"}),
    "su": frozenset({"subordinate", "subordinator"}),
    "ti": frozenset({"end", "subordination"}),
    "troz": frozenset({"because"}),
    "truq": frozenset({"concessive"}),
    "va": frozenset({"interrogative"}),
    "ve": frozenset({"future", "tense"}),
    "vi": frozenset({"animate"}),
    "vrem": frozenset({"after"}),
    "vro": frozenset({"relativizer"}),
    "xa": frozenset({"evidential", "witnessed"}),
    "xe": frozenset({"evidential", "inferred"}),
    "xen": frozenset({"and"}),
    "xo": frozenset({"assumed", "evidential"}),
    "zre": frozenset({"relativizer"}),
    "zu": frozenset({"mirative"}),
}
REVIEWED_NUMERAL_MAPPINGS = {
    "zero": "nul",
    "one": "ca",
    "two": "vriq",
    "three": "prit",
    "four": "qang",
    "five": "cum",
}
NON_INFINITIVE_TO_HEADS = frozenset(
    {"a", "an", "any", "many", "much", "one", "some", "the", "this", "that"}
)


def normalize_part_of_speech(value: Optional[str]) -> Optional[str]:
    """Normalize a controlled POS value; ``None`` means explicitly unknown."""
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"", "none", "null", "unknown"}:
        return None
    if normalized not in PARTS_OF_SPEECH:
        allowed = ", ".join(sorted(PARTS_OF_SPEECH))
        raise ValueError(f"unknown part of speech {value!r}; expected one of: {allowed}")
    return normalized


def _reviewed_pronoun_root(english_key: str) -> Optional[str]:
    spec = DEFAULT_GRAMMAR.english_pronouns.get(english_key)
    if spec is None:
        return None
    return DEFAULT_GRAMMAR.pronouns[spec[0]]


def infer_mapping_part_of_speech(
    english_key: str,
    root: str,
    meaning: str,
    category: str,
) -> Optional[tuple[str, str]]:
    """Return deterministic POS evidence for one English-key/root sense.

    POS belongs to a mapping rather than a Xenari root: roots such as ``toq``
    legitimately cover both noun and verb senses. Unknown or ambiguous senses
    remain NULL for curator review.
    """
    key = " ".join((english_key or "").strip().lower().split())
    root = (root or "").strip().lower()
    meaning_clean = " ".join((meaning or "").strip().lower().split())

    pronoun_root = _reviewed_pronoun_root(key)
    if pronoun_root == root:
        return "pronoun", "reviewed English-pronoun mapping"
    if REVIEWED_NUMERAL_MAPPINGS.get(key) == root:
        return "numeral", "reviewed base-6 numeral mapping"
    if key in REVIEWED_PARTICLE_KEYS_BY_ROOT.get(root, ()):
        return "particle", "reviewed grammar-particle mapping"
    if DEFAULT_GRAMMAR.verb_roots.get(key) == root:
        return "verb", "reviewed translator verb mapping"

    infinitive = re.match(r"^to\s+([a-z][a-z'-]*)\b", meaning_clean)
    if infinitive and infinitive.group(1) not in NON_INFINITIVE_TO_HEADS:
        if key == infinitive.group(1):
            return "verb", "English key matches definition infinitive head"

    explicit_labels = (
        ("adjective", ("(adjective", "adjective:", "adjectival")),
        ("adverb", ("(adverb", "adverb:", "adverbial")),
        ("interjection", ("(interjection", "interjection:")),
        ("ideophone", ("(ideophone", "ideophone:")),
        ("pronoun", ("(pronoun", "pronoun:")),
        ("numeral", ("(numeral", "numeral:")),
    )
    headword = re.split(r"\s*[(/,;—]\s*", meaning_clean, maxsplit=1)[0]
    for part_of_speech, markers in explicit_labels:
        if key == headword and any(marker in meaning_clean for marker in markers):
            return part_of_speech, f"definition explicitly labels {part_of_speech}"

    return None


class PartOfSpeechMixin:
    """Schema migration, validation, reporting, and conservative POS backfill."""

    def _has_part_of_speech_column(self) -> bool:
        return any(
            row["name"] == "part_of_speech"
            for row in self.conn.execute("PRAGMA table_info(english_map)").fetchall()
        )

    def _ensure_part_of_speech_schema(self) -> None:
        if not self._has_part_of_speech_column():
            values = ", ".join(repr(value) for value in sorted(PARTS_OF_SPEECH))
            self.conn.execute(
                "ALTER TABLE english_map ADD COLUMN part_of_speech TEXT "
                f"CHECK (part_of_speech IS NULL OR part_of_speech IN ({values}))"
            )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_english_part_of_speech "
            "ON english_map(part_of_speech)"
        )

    def part_of_speech_proposals(self) -> list[dict[str, object]]:
        """Return high-confidence proposals for unknown English mapping senses."""
        if not self._has_part_of_speech_column():
            return []
        proposals = []
        rows = self.conn.execute(
            """SELECT e.id, e.english_key, r.root, r.meaning, r.category
               FROM english_map e
               JOIN roots r ON r.id = e.root_id
               WHERE e.part_of_speech IS NULL
               ORDER BY e.english_key, r.root"""
        ).fetchall()
        for row in rows:
            inferred = infer_mapping_part_of_speech(
                row["english_key"], row["root"], row["meaning"], row["category"]
            )
            if inferred is None:
                continue
            part_of_speech, reason = inferred
            proposals.append(
                {
                    "mapping_id": row["id"],
                    "english_key": row["english_key"],
                    "root": row["root"],
                    "part_of_speech": part_of_speech,
                    "reason": reason,
                }
            )
        return proposals

    def part_of_speech_report(self) -> dict[str, object]:
        """Return sense-level schema, coverage, vocabulary, and validation data."""
        total = self.conn.execute("SELECT COUNT(*) FROM english_map").fetchone()[0]
        if not self._has_part_of_speech_column():
            return {
                "schema_present": False,
                "total": total,
                "annotated": 0,
                "unknown": total,
                "invalid": [],
                "counts": {},
                "controlled_vocabulary": sorted(PARTS_OF_SPEECH),
            }

        counts: Counter[str] = Counter()
        invalid = []
        rows = self.conn.execute(
            """SELECT e.english_key, e.part_of_speech, r.root
               FROM english_map e
               JOIN roots r ON r.id = e.root_id
               WHERE e.part_of_speech IS NOT NULL"""
        )
        for row in rows:
            value = row["part_of_speech"]
            if value in PARTS_OF_SPEECH:
                counts[value] += 1
            else:
                invalid.append(
                    {
                        "english_key": row["english_key"],
                        "root": row["root"],
                        "part_of_speech": value,
                    }
                )
        annotated = sum(counts.values())
        return {
            "schema_present": True,
            "total": total,
            "annotated": annotated,
            "unknown": total - annotated - len(invalid),
            "invalid": invalid,
            "counts": dict(sorted(counts.items())),
            "controlled_vocabulary": sorted(PARTS_OF_SPEECH),
        }

    def backfill_parts_of_speech(self, *, apply: bool = False) -> dict[str, object]:
        """Preview or apply deterministic proposals to NULL mapping senses only."""
        if not self._has_part_of_speech_column():
            raise RuntimeError(
                "part_of_speech schema is missing; reopen this database writable to migrate it"
            )
        proposals = self.part_of_speech_proposals()
        proposed_counts = dict(
            sorted(Counter(str(item["part_of_speech"]) for item in proposals).items())
        )
        if apply:
            if self.read_only:
                raise RuntimeError("cannot backfill part of speech on a read-only database")
            if proposals:
                self._backup_before_mutation("pos-backfill")
            with self.conn:
                self.conn.executemany(
                    """UPDATE english_map
                       SET part_of_speech = ?
                       WHERE id = ? AND part_of_speech IS NULL""",
                    [
                        (item["part_of_speech"], item["mapping_id"])
                        for item in proposals
                    ],
                )
                self.conn.execute(
                    """INSERT INTO tool_meta (key, value, updated_at)
                       VALUES ('pos_backfill_version', ?, datetime('now'))
                       ON CONFLICT(key) DO UPDATE SET
                         value = excluded.value,
                         updated_at = excluded.updated_at""",
                    (POS_BACKFILL_VERSION,),
                )
        report = self.part_of_speech_report()
        return {
            "applied": apply,
            "proposal_count": len(proposals),
            "proposed_counts": proposed_counts,
            "coverage": report,
            "proposals": proposals,
        }

    def mappings_by_part_of_speech(
        self, part_of_speech: str, limit: int = 100
    ) -> list[dict[str, object]]:
        """Query curated English senses by controlled POS."""
        normalized = normalize_part_of_speech(part_of_speech)
        if normalized is None or not self._has_part_of_speech_column():
            return []
        rows = self.conn.execute(
            """SELECT e.english_key, r.root, r.meaning, r.category,
                      e.part_of_speech
               FROM english_map e
               JOIN roots r ON r.id = e.root_id
               WHERE e.part_of_speech = ?
               ORDER BY e.english_key, r.root
               LIMIT ?""",
            (normalized, max(limit, 0)),
        ).fetchall()
        return [dict(row) for row in rows]

    def set_mapping_part_of_speech(
        self,
        english_key: str,
        root: str,
        part_of_speech: Optional[str],
    ) -> bool:
        """Set or clear curator-reviewed POS for one English-key/root sense."""
        if self.read_only:
            raise RuntimeError("cannot set part of speech on a read-only database")
        normalized = normalize_part_of_speech(part_of_speech)
        row = self.conn.execute(
            """SELECT e.id
               FROM english_map e JOIN roots r ON r.id = e.root_id
               WHERE e.english_key = ? AND r.root = ?""",
            (english_key.lower().strip(), root.strip()),
        ).fetchone()
        if row is None:
            return False
        self._backup_before_mutation("pos-set")
        cursor = self.conn.execute(
            "UPDATE english_map SET part_of_speech = ? WHERE id = ?",
            (normalized, row["id"]),
        )
        self.conn.commit()
        return cursor.rowcount == 1

    def parts_of_speech_for_root(self, root: str) -> list[str]:
        """Return the curated POS union for a potentially polysemous root."""
        if not self._has_part_of_speech_column():
            return []
        rows = self.conn.execute(
            """SELECT DISTINCT e.part_of_speech
               FROM english_map e JOIN roots r ON r.id = e.root_id
               WHERE r.root = ? AND e.part_of_speech IS NOT NULL
               ORDER BY e.part_of_speech""",
            (root,),
        ).fetchall()
        return [row["part_of_speech"] for row in rows]

    def attested_verb_roots(self) -> set[str]:
        """Return roots with at least one curator-backed verb sense."""
        if not self._has_part_of_speech_column():
            return set()
        return {
            row["root"]
            for row in self.conn.execute(
                """SELECT DISTINCT r.root
                   FROM english_map e JOIN roots r ON r.id = e.root_id
                   WHERE e.part_of_speech = 'verb'"""
            )
        }
