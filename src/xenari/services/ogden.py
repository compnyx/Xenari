"""Pinned Ogden Basic English coverage auditing for Xenari."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..paths import OGDEN_BASIC_ENGLISH


def _source_slots(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the source-order groups while retaining stable slot IDs."""
    return [entry for group in data.get("groups", []) for entry in group.get("entries", [])]


def _source_hash(slots: list[dict[str, Any]]) -> str:
    """Hash source slots only, so curation metadata cannot rewrite the source list."""
    normalized = [
        {"slot_id": slot["slot_id"], "forms": slot["forms"]}
        for slot in slots
    ]
    encoded = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _direct_mapping_rows(owner: Any, english: str, root: str) -> list[Any]:
    return owner.db.conn.execute(
        """SELECT e.part_of_speech
           FROM english_map e
           JOIN roots r ON r.id = e.root_id
           WHERE e.english_key = ? AND r.root = ?""",
        (english, root),
    ).fetchall()


class OgdenBaselineMixin:
    """Validate deliberate, reversible coverage of Ogden's 850 source slots."""

    def ogden_baseline_report(self, *, strict: bool = False) -> dict[str, object]:
        """Return a data-first coverage report without mutating canon.

        A slot becomes approved only when its exact direct English-map sense,
        POS, preferred root, and a full forward/reverse sentence fixture all
        agree. Unapproved slots remain an explicit review queue rather than
        being counted by fuzzy definition lookup.
        """
        try:
            data = json.loads(OGDEN_BASIC_ENGLISH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "schema": "xenari.ogden-baseline-report.v1",
                "ok": False,
                "errors": [f"could not load Ogden baseline: {exc}"],
            }

        errors: list[str] = []
        slots = _source_slots(data)
        source = data.get("source", {})
        expected_counts = source.get("slot_counts", {})
        actual_counts = {
            group.get("id", "unknown"): len(group.get("entries", []))
            for group in data.get("groups", [])
        }
        if actual_counts != expected_counts:
            errors.append(
                f"source slot counts differ: expected {expected_counts}, got {actual_counts}"
            )

        accepted_forms = [form for slot in slots for form in slot.get("forms", [])]
        if len(slots) != 850:
            errors.append(f"expected 850 source slots, got {len(slots)}")
        if len(accepted_forms) != source.get("accepted_form_count"):
            errors.append(
                "accepted form count differs: "
                f"expected {source.get('accepted_form_count')}, got {len(accepted_forms)}"
            )
        if len(set(accepted_forms)) != len(accepted_forms):
            errors.append("source slots contain duplicate accepted forms")
        source_hash = _source_hash(slots)
        if source_hash != source.get("normalized_slot_sha256"):
            errors.append("normalized source slot hash does not match the pinned manifest")

        slots_by_id = {slot.get("slot_id"): slot for slot in slots}
        if len(slots_by_id) != len(slots):
            errors.append("source slots contain duplicate or missing slot IDs")

        approvals = data.get("approvals", {})
        unsupported = data.get("unsupported", {})
        if not isinstance(approvals, dict):
            errors.append("approvals must be an object keyed by source slot ID")
            approvals = {}
        if not isinstance(unsupported, dict):
            errors.append("unsupported must be an object keyed by source slot ID")
            unsupported = {}

        for slot_id in set(approvals) | set(unsupported):
            if slot_id not in slots_by_id:
                errors.append(f"curation metadata refers to unknown slot {slot_id!r}")
        for slot_id in set(approvals) & set(unsupported):
            errors.append(f"slot {slot_id!r} is both approved and unsupported")
        for slot_id, item in unsupported.items():
            if not isinstance(item, dict) or not str(item.get("reason", "")).strip():
                errors.append(f"unsupported slot {slot_id!r} needs a deliberate reason")

        direct_forms = 0
        pos_matched_forms = 0
        for slot in slots:
            expected_pos = slot.get("part_of_speech")
            for form in slot.get("forms", []):
                rows = self.db.conn.execute(
                    """SELECT e.part_of_speech
                       FROM english_map e
                       WHERE e.english_key = ?""",
                    (form,),
                ).fetchall()
                if rows:
                    direct_forms += 1
                if any(row["part_of_speech"] == expected_pos for row in rows):
                    pos_matched_forms += 1

        approved_failures: list[str] = []
        for slot_id, approval in approvals.items():
            slot = slots_by_id.get(slot_id)
            if slot is None or not isinstance(approval, dict):
                approved_failures.append(f"{slot_id}: invalid approval record")
                continue
            root = str(approval.get("root", "")).strip()
            fixture = approval.get("fixture")
            if not root:
                approved_failures.append(f"{slot_id}: approval has no expected root")
                continue
            if not isinstance(fixture, dict) or not all(
                isinstance(fixture.get(key), str) and fixture[key].strip()
                for key in ("english", "xenari", "reverse")
            ):
                approved_failures.append(f"{slot_id}: approval needs a complete sentence fixture")
                continue

            expected_pos = slot["part_of_speech"]
            for form in slot["forms"]:
                rows = _direct_mapping_rows(self, form, root)
                if not any(row["part_of_speech"] == expected_pos for row in rows):
                    approved_failures.append(
                        f"{slot_id}: {form!r} lacks direct {expected_pos} mapping to {root}"
                    )
                selected, _meaning = self.lookup(
                    form, part_of_speech=expected_pos
                )
                if selected != root:
                    approved_failures.append(
                        f"{slot_id}: lookup {form!r} selected {selected!r}, expected {root!r}"
                    )

            actual_xenari = self.speak(fixture["english"], evidential="assumed")
            if actual_xenari != fixture["xenari"]:
                approved_failures.append(
                    f"{slot_id}: forward fixture changed: expected {fixture['xenari']!r}, "
                    f"got {actual_xenari!r}"
                )
            actual_reverse = self.reverse(fixture["xenari"])
            if actual_reverse != fixture["reverse"]:
                approved_failures.append(
                    f"{slot_id}: reverse fixture changed: expected {fixture['reverse']!r}, "
                    f"got {actual_reverse!r}"
                )

        approved_ids = set(approvals) & set(slots_by_id)
        unsupported_ids = set(unsupported) & set(slots_by_id)
        pending_ids = set(slots_by_id) - approved_ids - unsupported_ids
        status_counts = {
            "approved": len(approved_ids),
            "pending": len(pending_ids),
            "unsupported": len(unsupported_ids),
        }
        errors.extend(approved_failures)
        strict_blockers = sorted(pending_ids | unsupported_ids)
        ok = not errors and (not strict or not strict_blockers)
        return {
            "schema": "xenari.ogden-baseline-report.v1",
            "ok": ok,
            "strict": strict,
            "source": {
                "slot_count": len(slots),
                "accepted_form_count": len(accepted_forms),
                "normalized_slot_sha256": source_hash,
            },
            "coverage": {
                "statuses": status_counts,
                "direct_mapping_forms": direct_forms,
                "pos_matched_forms": pos_matched_forms,
            },
            "approved_failures": approved_failures,
            "strict_blockers": strict_blockers if strict else [],
            "errors": errors,
        }

    def ogden_baseline(self, *, strict: bool = False) -> tuple[bool, str]:
        """Render the source-pinned coverage report for people and CLI users."""
        report = self.ogden_baseline_report(strict=strict)
        if "source" not in report:
            return False, "Ogden Basic English baseline\nstatus: failed\n" + "\n".join(
                report.get("errors", [])
            )
        coverage = report["coverage"]
        statuses = coverage["statuses"]
        lines = [
            "Ogden Basic English baseline",
            f"Source slots: {report['source']['slot_count']} "
            f"({report['source']['accepted_form_count']} accepted forms)",
            "Coverage: "
            f"{statuses['approved']} approved, {statuses['pending']} pending, "
            f"{statuses['unsupported']} unsupported",
            "Direct exact mappings: "
            f"{coverage['direct_mapping_forms']} / {report['source']['accepted_form_count']}",
            "POS-matched direct mappings: "
            f"{coverage['pos_matched_forms']} / {report['source']['accepted_form_count']}",
        ]
        if report["approved_failures"]:
            lines.append("Approved-slot failures:")
            lines.extend(f"  - {item}" for item in report["approved_failures"])
        if strict and report["strict_blockers"]:
            lines.append(f"Strict blockers: {len(report['strict_blockers'])} unapproved slot(s)")
        lines.extend(
            f"ERROR: {item}" for item in report["errors"] if item not in report["approved_failures"]
        )
        lines.append(
            "status: ok"
            if report["ok"]
            else "status: in progress"
            if not report["errors"]
            else "status: failed"
        )
        return bool(report["ok"]), "\n".join(lines)
