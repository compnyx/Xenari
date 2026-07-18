import sqlite3
from typing import Tuple


class RelationsMixin:
    def add_compound(self, compound_root: str, components: list) -> bool:
        """Register a compound root's component parts.
        components: list of (root, position) tuples or just list of roots."""
        row = self.conn.execute("SELECT id FROM roots WHERE root = ?", (compound_root,)).fetchone()
        if not row:
            print(f"compound root '{compound_root}' not found in DB")
            return False

        # Clear existing compound parts for this root
        self.conn.execute("DELETE FROM compounds WHERE compound_root = ?", (compound_root,))

        for i, comp in enumerate(components):
            if isinstance(comp, tuple):
                comp_root, pos = comp
            else:
                comp_root, pos = comp, i
            # verify component exists
            comp_row = self.conn.execute("SELECT 1 FROM roots WHERE root = ?", (comp_root,)).fetchone()
            if not comp_row:
                print(f"component root '{comp_root}' not found, skipping")
                continue
            self.conn.execute(
                "INSERT INTO compounds (compound_root, component_root, position) VALUES (?, ?, ?)",
                (compound_root, comp_root, pos)
            )

        self.conn.commit()
        return True

    def get_compound_parts(self, compound_root: str) -> list:
        """Get the component parts of a compound root."""
        rows = self.conn.execute(
            "SELECT component_root, position FROM compounds WHERE compound_root = ? ORDER BY position",
            (compound_root,)
        ).fetchall()
        return [(r["component_root"], r["position"]) for r in rows]

    def find_compounds_using(self, component_root: str) -> list:
        """Find all compounds that use a given root as a component."""
        rows = self.conn.execute(
            "SELECT compound_root FROM compounds WHERE component_root = ? ORDER BY compound_root",
            (component_root,)
        ).fetchall()
        return [r["compound_root"] for r in rows]

    def add_relation(self, root_a: str, root_b: str, relation: str, notes: str = None) -> bool:
        """Add a semantic relation between two roots.
        relation: synonym, antonym, related, derivation, see_also"""
        for r in (root_a, root_b):
            row = self.conn.execute("SELECT 1 FROM roots WHERE root = ?", (r,)).fetchone()
            if not row:
                print(f"root '{r}' not found")
                return False
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO semantic_relations (root_a, root_b, relation, notes) VALUES (?, ?, ?, ?)",
                (root_a, root_b, relation, notes)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def relate(
        self,
        root_a: str,
        root_b: str,
        relation: str,
        notes: str = None,
        yes: bool = False,
    ) -> Tuple[bool, str]:
        """Preview or explicitly record a curator-selected semantic relation."""
        allowed = {"synonym", "antonym", "related", "derivation", "see_also", "register_variant"}
        lines = [f"Semantic relation preview: {root_a} --{relation}--> {root_b}"]
        if relation not in allowed:
            lines.append(f"Unknown relation type. Choose one of: {', '.join(sorted(allowed))}")
            return False, "\n".join(lines)
        if root_a == root_b:
            lines.append("A root cannot be related to itself.")
            return False, "\n".join(lines)
        rows = [self.lookup_root(root) for root in (root_a, root_b)]
        if not all(rows):
            missing = [root for root, row in zip((root_a, root_b), rows) if not row]
            lines.append(f"Unknown root(s): {', '.join(missing)}")
            return False, "\n".join(lines)
        for row in rows:
            lines.append(f"  - {row['root']}[{row['category']}]: {row['meaning']}")
        if notes:
            lines.append(f"Notes: {notes}")
        lines.append("This relation is a curator assertion; the tool did not infer it as fact.")
        existing = self.conn.execute(
            """SELECT 1 FROM semantic_relations
               WHERE ((root_a = ? AND root_b = ?) OR (root_a = ? AND root_b = ?))
                 AND relation = ?""",
            (root_a, root_b, root_b, root_a, relation),
        ).fetchone()
        if existing:
            lines.append("Relation already exists.")
            return True, "\n".join(lines)
        if not yes:
            lines.append("PREVIEW ONLY: no database write. Re-run with --yes to record this assertion.")
            return True, "\n".join(lines)

        backup_path = self._backup_before_mutation("relate")
        if not self.add_relation(root_a, root_b, relation, notes=notes):
            lines.append("Failed to write relation.")
            return False, "\n".join(lines)
        lines.append(f"Backup: {backup_path}")
        lines.append("Wrote 1 semantic relation.")
        return True, "\n".join(lines)

    def get_relations(self, root: str) -> list:
        """Get all semantic relations for a root."""
        rows = self.conn.execute(
            "SELECT root_a, root_b, relation, notes FROM semantic_relations WHERE root_a = ? OR root_b = ?",
            (root, root)
        ).fetchall()
        return [dict(r) for r in rows]

    def relations_report(self, root: str) -> Tuple[bool, str]:
        """Summarize semantic and compound relationships for a root."""
        row = self.lookup_root(root)
        if not row:
            return False, f"root '{root}' not found"
        relations = self.get_relations(root)
        parts = self.get_compound_parts(root)
        compounds_using = self.find_compounds_using(root)
        lines = [f"{root} — {row['meaning']} [{row['category']}]"]
        lines.append("Relations:")
        if not relations:
            lines.append("  none")
        for rel in relations:
            other = rel["root_b"] if rel["root_a"] == root else rel["root_a"]
            other_row = self.lookup_root(other) or {"meaning": "unknown"}
            note = f" ({rel['notes']})" if rel["notes"] else ""
            lines.append(f"  - {rel['relation']}: {other} — {other_row['meaning']}{note}")
        lines.append("Compound parts:")
        if parts:
            for component, pos in parts:
                comp_row = self.lookup_root(component) or {"meaning": "unknown"}
                lines.append(f"  - {pos}: {component} — {comp_row['meaning']}")
        else:
            lines.append("  none")
        lines.append("Compounds using this root:")
        if compounds_using:
            for compound in compounds_using:
                comp_row = self.lookup_root(compound) or {"meaning": "unknown"}
                lines.append(f"  - {compound} — {comp_row['meaning']}")
        else:
            lines.append("  none")
        head = self._audit_headword(row["meaning"])
        near = [
            item for item in self.near_meanings(head or row["meaning"], limit=6)
            if item["root"] != root
        ]
        lines.append("Review-near meanings:")
        if near:
            for item in near[:5]:
                lines.append(
                    f"  - {item['root']} — {item['meaning']} "
                    f"[{item['category']}] score={item.get('score', 0)}"
                )
            lines.append("  note: these are search hints, not curated semantic relations")
        else:
            lines.append("  none")
        return True, "\n".join(lines)
