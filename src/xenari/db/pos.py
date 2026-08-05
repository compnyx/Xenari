"""Sense-level part-of-speech metadata and conservative curation support."""

import re
from collections import Counter
from typing import Iterable, Mapping, Optional

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
        if key in {infinitive.group(1), f"to {infinitive.group(1)}"}:
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

    def unknown_part_of_speech_mappings(self, limit: int = 20) -> list[dict[str, object]]:
        """Return a bounded curator queue of still-untyped mapping senses."""
        if not self._has_part_of_speech_column():
            return []
        rows = self.conn.execute(
            """SELECT e.english_key, r.root, r.meaning, r.category, e.context_note
               FROM english_map e
               JOIN roots r ON r.id = e.root_id
               WHERE e.part_of_speech IS NULL
               ORDER BY e.english_key, r.root
               LIMIT ?""",
            (max(limit, 0),),
        ).fetchall()
        return [dict(row) for row in rows]

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

    def set_mapping_parts_of_speech(
        self,
        mappings: Iterable[tuple[str, str, str]],
        *,
        operation: str = "pos-batch",
    ) -> dict[str, object]:
        """Atomically apply a reviewed POS batch with one canonical backup."""
        if self.read_only:
            raise RuntimeError("cannot set part of speech on a read-only database")

        resolved: list[tuple[str, int]] = []
        unchanged = 0
        seen: set[tuple[str, str]] = set()
        for english_key, root, part_of_speech in mappings:
            key = english_key.lower().strip()
            canonical_root = root.strip()
            pair = (key, canonical_root)
            if pair in seen:
                raise ValueError(f"duplicate POS batch mapping: {key!r} -> {canonical_root!r}")
            seen.add(pair)
            normalized = normalize_part_of_speech(part_of_speech)
            if normalized is None:
                raise ValueError(f"POS batch mapping cannot be unknown: {key!r} -> {canonical_root!r}")
            row = self.conn.execute(
                """SELECT e.id, e.part_of_speech
                   FROM english_map e JOIN roots r ON r.id = e.root_id
                   WHERE e.english_key = ? AND r.root = ?""",
                pair,
            ).fetchone()
            if row is None:
                raise ValueError(f"missing POS batch mapping: {key!r} -> {canonical_root!r}")
            current = row["part_of_speech"]
            if current is not None and current != normalized:
                raise ValueError(
                    f"conflicting POS batch mapping: {key!r} -> {canonical_root!r} "
                    f"is already {current!r}, not {normalized!r}"
                )
            if current == normalized:
                unchanged += 1
            else:
                resolved.append((normalized, row["id"]))

        backup_path = None
        if resolved:
            backup_path = self._backup_before_mutation(operation)
            before_changes = self.conn.total_changes
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                self.conn.executemany(
                    """UPDATE english_map SET part_of_speech = ?
                       WHERE id = ? AND part_of_speech IS NULL""",
                    resolved,
                )
                applied = self.conn.total_changes - before_changes
                if applied != len(resolved):
                    raise RuntimeError(
                        f"POS batch changed {applied} rows; expected {len(resolved)}"
                    )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
        else:
            applied = 0

        return {
            "mapping_count": len(seen),
            "applied": applied,
            "unchanged": unchanged,
            "backup": str(backup_path) if backup_path is not None else None,
        }

    def apply_mapping_curation_batch(
        self,
        actions: Iterable[Mapping[str, object]],
        *,
        operation: str = "mapping-curation-batch",
    ) -> dict[str, object]:
        """Atomically apply exact mapping-level POS curation actions.

        The batch deliberately operates on ``english_map`` rows only; roots
        are never deleted or rewritten. Every mutation names the exact source
        English key, root, and expected current POS (``None`` by default).
        Supported action names are:

        - ``tag`` / ``tag_primary``
        - ``delete`` / ``delete_mapping``
        - ``rename_and_tag`` / ``rename_mapping_and_tag``
        - ``merge``, ``normalize``, or ``refine`` (the same exact rename+tag)
        - ``add_mapping`` / ``add_split_mapping`` (requires an exact
          ``source_english_key``)

        Rename actions use ``new_english_key`` (``replacement_english_key``
        is accepted for fixture manifests). Split actions add a separately
        tagged mapping to an existing root. Its source row is a snapshot
        anchor and may itself be tagged, renamed, or removed by the same
        atomic batch; the root is never removed.
        The complete plan is validated both before the backup and again under
        ``BEGIN IMMEDIATE``; any mismatch or SQLite error rolls back the whole
        transaction.
        """
        if self.read_only:
            raise RuntimeError("cannot curate mappings on a read-only database")
        if not self._has_part_of_speech_column():
            raise RuntimeError("part-of-speech schema is missing")

        aliases = {
            "tag": "tag",
            "tag_mapping": "tag",
            "tag_primary": "tag",
            "delete": "delete",
            "delete_mapping": "delete",
            "rename_and_tag": "rename",
            "rename_mapping_and_tag": "rename",
            "merge": "rename",
            "merge_mapping": "rename",
            "normalize": "rename",
            "normalize_mapping": "rename",
            "refine": "rename",
            "refine_mapping": "rename",
            "replace": "rename",
            "replace_mapping": "rename",
            "add_mapping": "split",
            "add_split_mapping": "split",
            "split_mapping": "split",
        }

        def clean_key(value: object, field: str) -> str:
            if not isinstance(value, str):
                raise ValueError(f"mapping curation {field} must be a string")
            cleaned = value.lower().strip()
            if not cleaned:
                raise ValueError(f"mapping curation {field} cannot be empty")
            return cleaned

        def clean_root(value: object) -> str:
            if not isinstance(value, str):
                raise ValueError("mapping curation root must be a string")
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("mapping curation root cannot be empty")
            return cleaned

        def clean_pos(
            value: object, field: str, *, allow_none: bool = False
        ) -> Optional[str]:
            if value is None:
                if allow_none:
                    return None
                raise ValueError(f"mapping curation {field} cannot be unknown")
            if not isinstance(value, str):
                raise ValueError(
                    f"mapping curation {field} must be a string or null"
                )
            normalized = normalize_part_of_speech(value)
            if normalized is None and not allow_none:
                raise ValueError(f"mapping curation {field} cannot be unknown")
            return normalized

        normalized_actions: list[dict[str, object]] = []
        for index, raw in enumerate(actions):
            if not isinstance(raw, Mapping):
                raise ValueError(
                    f"mapping curation action {index} must be a mapping"
                )
            requested = raw.get("action")
            if not isinstance(requested, str) or requested not in aliases:
                raise ValueError(
                    f"unknown mapping curation action {requested!r} at index {index}"
                )
            kind = aliases[requested]
            root = clean_root(raw.get("root"))
            expected = clean_pos(
                raw.get("expected_part_of_speech"),
                "expected_part_of_speech",
                allow_none=True,
            )

            if kind == "split":
                source_key = clean_key(
                    raw.get("source_english_key"), "source_english_key"
                )
                target_value = raw.get("new_english_key", raw.get("english_key"))
                target_key = clean_key(target_value, "new_english_key")
                part_of_speech = clean_pos(
                    raw.get(
                        "part_of_speech",
                        raw.get("replacement_pos", raw.get("pos")),
                    ),
                    "part_of_speech",
                )
                context_note = raw.get("context_note")
                if context_note is not None and not isinstance(context_note, str):
                    raise ValueError(
                        "mapping curation context_note must be a string or null"
                    )
                normalized_actions.append(
                    {
                        "kind": kind,
                        "requested_action": requested,
                        "root": root,
                        "source_key": source_key,
                        "target_key": target_key,
                        "part_of_speech": part_of_speech,
                        "expected": expected,
                        "context_note": context_note,
                    }
                )
                continue

            source_key = clean_key(raw.get("english_key"), "english_key")
            item: dict[str, object] = {
                "kind": kind,
                "requested_action": requested,
                "root": root,
                "source_key": source_key,
                "expected": expected,
            }
            if kind in {"tag", "rename"}:
                part_of_speech = clean_pos(
                    raw.get(
                        "part_of_speech",
                        raw.get("replacement_pos", raw.get("pos")),
                    ),
                    "part_of_speech",
                )
                item["part_of_speech"] = part_of_speech
                if kind == "tag" and expected == part_of_speech:
                    raise ValueError(
                        f"mapping curation tag is a no-op: {source_key!r} -> {root!r}"
                    )
            if kind == "rename":
                target_value = raw.get(
                    "new_english_key", raw.get("replacement_english_key")
                )
                target_key = clean_key(target_value, "new_english_key")
                if target_key == source_key:
                    raise ValueError(
                        f"mapping curation rename is a no-op: {source_key!r} -> {root!r}"
                    )
                item["target_key"] = target_key
            normalized_actions.append(item)

        if not normalized_actions:
            return {
                "action_count": 0,
                "applied": 0,
                "changed_rows": 0,
                "counts": {},
                "backup": None,
            }

        def resolve_plan() -> list[dict[str, object]]:
            plan: list[dict[str, object]] = []
            mutated_sources: dict[tuple[str, str], str] = {}
            created_targets: set[tuple[str, str]] = set()
            for item in normalized_actions:
                root = str(item["root"])
                source_key = str(item["source_key"])
                root_row = self.conn.execute(
                    "SELECT id FROM roots WHERE root = ?", (root,)
                ).fetchone()
                if root_row is None:
                    raise ValueError(f"missing mapping curation root: {root!r}")
                root_id = root_row["id"]
                source = self.conn.execute(
                    """SELECT id, part_of_speech FROM english_map
                       WHERE english_key = ? AND root_id = ?""",
                    (source_key, root_id),
                ).fetchone()
                if source is None:
                    raise ValueError(
                        f"missing mapping curation source: {source_key!r} -> {root!r}"
                    )
                expected = item["expected"]
                if source["part_of_speech"] != expected:
                    raise ValueError(
                        f"mapping curation source mismatch: {source_key!r} -> {root!r} "
                        f"is {source['part_of_speech']!r}, expected {expected!r}"
                    )

                planned = dict(item)
                planned["root_id"] = root_id
                planned["source_id"] = source["id"]
                source_pair = (source_key, root)
                if item["kind"] == "split":
                    # A split only needs the source to establish the exact
                    # root and pre-batch POS. The source row may have its own
                    # terminal decision in this transaction.
                    pass
                else:
                    if source_pair in mutated_sources:
                        raise ValueError(
                            f"duplicate mapping curation source: {source_key!r} -> {root!r}"
                        )
                    mutated_sources[source_pair] = str(item["kind"])

                if item["kind"] in {"rename", "split"}:
                    target_key = str(item["target_key"])
                    target_pair = (target_key, root)
                    if target_pair in created_targets:
                        raise ValueError(
                            f"duplicate mapping curation target: {target_key!r} -> {root!r}"
                        )
                    created_targets.add(target_pair)
                    existing = self.conn.execute(
                        """SELECT id FROM english_map
                           WHERE english_key = ? AND root_id = ?""",
                        (target_key, root_id),
                    ).fetchone()
                    if existing is not None:
                        raise ValueError(
                            f"conflicting mapping curation target already exists: "
                            f"{target_key!r} -> {root!r}"
                        )
                plan.append(planned)
            return plan

        # Fail cheaply before producing a backup, then repeat the exact checks
        # under a write lock so another connection cannot invalidate the plan.
        resolve_plan()
        backup_path = self._backup_before_mutation(operation)
        before_changes = self.conn.total_changes
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            plan = resolve_plan()
            for item in plan:
                kind = item["kind"]
                if kind == "tag":
                    cursor = self.conn.execute(
                        "UPDATE english_map SET part_of_speech = ? WHERE id = ?",
                        (item["part_of_speech"], item["source_id"]),
                    )
                elif kind == "delete":
                    cursor = self.conn.execute(
                        "DELETE FROM english_map WHERE id = ?", (item["source_id"],)
                    )
                elif kind == "rename":
                    cursor = self.conn.execute(
                        """UPDATE english_map
                           SET english_key = ?, part_of_speech = ?
                           WHERE id = ?""",
                        (
                            item["target_key"],
                            item["part_of_speech"],
                            item["source_id"],
                        ),
                    )
                else:
                    cursor = self.conn.execute(
                        """INSERT INTO english_map
                           (english_key, root_id, context_note, part_of_speech)
                           VALUES (?, ?, ?, ?)""",
                        (
                            item["target_key"],
                            item["root_id"],
                            item["context_note"],
                            item["part_of_speech"],
                        ),
                    )
                if cursor.rowcount != 1:
                    raise RuntimeError(
                        f"mapping curation {kind} changed {cursor.rowcount} rows; expected 1"
                    )
            changed_rows = self.conn.total_changes - before_changes
            if changed_rows != len(plan):
                raise RuntimeError(
                    f"mapping curation changed {changed_rows} rows; expected {len(plan)}"
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        counts = Counter(str(item["kind"]) for item in normalized_actions)
        return {
            "action_count": len(normalized_actions),
            "applied": len(normalized_actions),
            "changed_rows": changed_rows,
            "counts": dict(sorted(counts.items())),
            "backup": str(backup_path),
        }

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
