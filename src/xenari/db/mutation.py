import datetime
import re
import sqlite3
from pathlib import Path
from typing import List, Tuple

from .categorization import CategorizationMixin
from .relations import RelationsMixin


class MutationMixin(CategorizationMixin, RelationsMixin):
    def add_root(self, english: str, root: str, meaning: str,
                 category: str = "Uncategorized",
                 source: str = None, notes: str = None,
                 extra_english_keys: List[str] = None,
                 dry_run: bool = False) -> Tuple[bool, List[str]]:
        """Add a root + english mapping. Returns (success, messages)."""
        key = english.lower().strip()
        msgs = []

        # Hard collision checks
        if self.has_english(key) and self.has_root(root):
            existing_root = self.conn.execute(
                "SELECT r.root FROM english_map e JOIN roots r ON r.id = e.root_id WHERE e.english_key = ?",
                (key,)
            ).fetchone()
            existing_meaning = self.conn.execute(
                "SELECT meaning FROM roots WHERE root = ?", (root,)
            ).fetchone()
            r = existing_root["root"] if existing_root else "?"
            m = existing_meaning["meaning"] if existing_meaning else "?"
            msgs.append(f"BLOCKED: '{key}' already maps to '{r}', and '{root}' already exists ({m})")
            return False, msgs

        if self.has_english(key):
            existing = self.conn.execute(
                "SELECT r.root FROM english_map e JOIN roots r ON r.id = e.root_id WHERE e.english_key = ?",
                (key,)
            ).fetchone()
            msgs.append(f"BLOCKED: '{key}' is already mapped to '{existing['root']}'. Use a different key or remove the old one.")
            return False, msgs

        if self.has_root(root):
            existing = self.conn.execute(
                "SELECT meaning FROM roots WHERE root = ?", (root,)
            ).fetchone()
            msgs.append(f"BLOCKED: root '{root}' already exists ({existing['meaning']}). Pick a different root.")
            return False, msgs

        # Soft warnings: stem near-match
        stem = self._stem(key)
        if stem != key:
            near = self.conn.execute(
                "SELECT e.english_key, r.root FROM english_map e JOIN roots r ON r.id = e.root_id"
            ).fetchall()
            for row in near:
                if self._stem(row["english_key"]) == stem:
                    msgs.append(f"WARNING: '{key}' looks like '{row['english_key']}' (already mapped to '{row['root']}'). Proceeding — context matters.")
                    break

        # Soft warnings: phonetic near-match
        all_roots = self.conn.execute("SELECT root, meaning FROM roots").fetchall()
        for row in all_roots:
            dist = self._edit_distance(root, row["root"])
            if 0 < dist <= 2:
                msgs.append(f"WARNING: root '{root}' is close to existing '{row['root']}' ({row['meaning']}). Check for typos? Proceeding anyway.")
                break

        # Phonotactic validation is a write gate, not advisory text.  A root
        # that fails canon shape checks must never reach the INSERT below.
        phon_issues = self.validate_phonotactics(root)
        if phon_issues:
            msgs.extend(f"BLOCKED: invalid root form: {pi}" for pi in phon_issues)
            return False, msgs

        if dry_run:
            msgs.append(f"DRY RUN: would add {root} — {meaning} (for '{english}') in [{category}]")
            return True, msgs

        # Insert
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        src = source or "tool"
        try:
            cur = self.conn.execute(
                "INSERT INTO roots (root, meaning, category, source, timestamp, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (root, meaning, category, src, ts, notes)
            )
            root_id = cur.lastrowid

            # Map the primary english key
            self.conn.execute(
                "INSERT OR IGNORE INTO english_map (english_key, root_id) VALUES (?, ?)",
                (key, root_id)
            )

            # Map extra english keys if provided
            if extra_english_keys:
                for ek in extra_english_keys:
                    ek = ek.lower().strip()
                    if ek and ek != key:
                        self.conn.execute(
                            "INSERT OR IGNORE INTO english_map (english_key, root_id) VALUES (?, ?)",
                            (ek, root_id)
                        )

            # Also auto-map individual words from the meaning (for backwards compat)
            for w in re.split(r"[ /,]+", meaning.lower().split("—")[0].strip()):
                w = w.strip()
                if w and len(w) > 1 and not self.has_english(w):
                    self.conn.execute(
                        "INSERT OR IGNORE INTO english_map (english_key, root_id) VALUES (?, ?)",
                        (w, root_id)
                    )

            self.conn.commit()
            msgs.append(f"Added: {root} — {meaning} (for '{english}') in [{category}]")
            return True, msgs

        except sqlite3.IntegrityError as e:
            msgs.append(f"DB error: {e}")
            return False, msgs

    def remove_root(self, root: str) -> bool:
        """Remove a root and all its english mappings."""
        row = self.conn.execute("SELECT id, meaning FROM roots WHERE root = ?", (root,)).fetchone()
        if not row:
            print(f"root '{root}' not found")
            return False
        self.conn.execute("DELETE FROM compounds WHERE compound_root = ? OR component_root = ?", (root, root))
        self.conn.execute("DELETE FROM semantic_relations WHERE root_a = ? OR root_b = ?", (root, root))
        self.conn.execute("DELETE FROM english_map WHERE root_id = ?", (row["id"],))
        self.conn.execute("DELETE FROM roots WHERE id = ?", (row["id"],))
        self.conn.commit()
        print(f"Removed: {root} ({row['meaning']})")
        return True

    def describe_remove_root(self, root: str) -> Tuple[bool, str]:
        """Preview the rows affected by removing a root."""
        row = self.conn.execute("SELECT id, root, meaning, category FROM roots WHERE root = ?", (root,)).fetchone()
        if not row:
            return False, f"root '{root}' not found"

        mappings = self.conn.execute(
            "SELECT english_key, context_note FROM english_map WHERE root_id = ? ORDER BY english_key",
            (row["id"],)
        ).fetchall()
        compounds = self.conn.execute(
            """SELECT compound_root, component_root, position
               FROM compounds
               WHERE compound_root = ? OR component_root = ?
               ORDER BY compound_root, position""",
            (root, root)
        ).fetchall()
        relations = self.conn.execute(
            """SELECT root_a, root_b, relation, notes
               FROM semantic_relations
               WHERE root_a = ? OR root_b = ?
               ORDER BY relation, root_a, root_b""",
            (root, root)
        ).fetchall()

        lines = [
            f"Remove preview for {row['root']} — {row['meaning']} [{row['category']}]",
            f"English mappings: {len(mappings)}",
        ]
        for mapping in mappings[:20]:
            note = f" ({mapping['context_note']})" if mapping["context_note"] else ""
            lines.append(f"  - {mapping['english_key']}{note}")
        if len(mappings) > 20:
            lines.append(f"  ... {len(mappings) - 20} more")

        lines.append(f"Compound rows: {len(compounds)}")
        for compound in compounds[:20]:
            lines.append(f"  - {compound['compound_root']} uses {compound['component_root']} at {compound['position']}")
        if len(compounds) > 20:
            lines.append(f"  ... {len(compounds) - 20} more")

        lines.append(f"Semantic relations: {len(relations)}")
        for relation in relations[:20]:
            note = f" ({relation['notes']})" if relation["notes"] else ""
            lines.append(f"  - {relation['root_a']} {relation['relation']} {relation['root_b']}{note}")
        if len(relations) > 20:
            lines.append(f"  ... {len(relations) - 20} more")

        return True, "\n".join(lines)

    def describe_english_mapping(self, english_key: str, root: str, context_note: str = None) -> Tuple[bool, str]:
        """Preview adding an English mapping to an existing root."""
        row = self.conn.execute("SELECT id, root, meaning FROM roots WHERE root = ?", (root,)).fetchone()
        if not row:
            return False, f"root '{root}' not found"
        key = english_key.lower().strip()
        existing = self.conn.execute(
            """SELECT r.root, r.meaning
               FROM english_map e JOIN roots r ON r.id = e.root_id
               WHERE e.english_key = ?
               ORDER BY r.root""",
            (key,)
        ).fetchall()
        lines = [f"Map preview: {key} -> {root} — {row['meaning']}"]
        if context_note:
            lines.append(f"Context note: {context_note}")
        if existing:
            lines.append(f"Existing mappings for '{key}':")
            for item in existing:
                lines.append(f"  - {item['root']} — {item['meaning']}")
        else:
            lines.append(f"No existing mappings for '{key}'.")
        return True, "\n".join(lines)

    def add_english_mapping(self, english_key: str, root: str, context_note: str = None) -> bool:
        """Add an english→root mapping to an existing root."""
        row = self.conn.execute("SELECT id FROM roots WHERE root = ?", (root,)).fetchone()
        if not row:
            print(f"root '{root}' not found")
            return False
        key = english_key.lower().strip()
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO english_map (english_key, root_id, context_note) VALUES (?, ?, ?)",
                (key, row["id"], context_note)
            )
            self.conn.commit()
            print(f"Mapped: {key} → {root}")
            return True
        except sqlite3.IntegrityError:
            print(f"'{key}' is already mapped")
            return False

    def _backup_before_mutation(self, operation: str) -> Path:
        """Create a consistent SQLite backup immediately before a curated write."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = self.db_path.with_name(
            f"{self.db_path.name}.{timestamp}.{operation}.bak"
        )
        self.conn.commit()
        backup = sqlite3.connect(str(backup_path))
        try:
            self.conn.backup(backup)
        finally:
            backup.close()
        return backup_path
