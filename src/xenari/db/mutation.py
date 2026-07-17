import datetime
import hashlib
import re
import shlex
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class MutationMixin:
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
            self._auto_export()
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

    def _category_rules(self) -> list:
        return [
            (["succubus", "feed", "brat", "horny", "goth", "kinky", "lewd", "submit",
              "dominant", "shameless", "needy", "clingy", "roleplay", "prad", "strem",
              "ngal", "zhrek", "ngrok", "zhem", "smek", "frez", "mben", "svet", "mrok"],
             "Succubus Culture & Feeding"),
            (["overfeed", "pathology", "fast soul"], "Succubus Culture & Feeding"),
            (["cooking", "kitchen", "boil", "fry", "bake", "chop", "stir", "spice",
              "recipe", "ingredient", "meal", "snack", "taste", "simmer", "grill"],
             "Plants & Food"),
            (["music", "sing", "song", "drum", "flute", "instrument", "rhythm",
              "melody", "beat", "harmony", "chorus", "boom", "sound", "noise"],
             "Arts & Culture"),
            (["hate", "jealous", "grief", "nostalgia", "contempt", "awe", "bored",
              "excit", "disappoint", "shame", "pride", "guilt", "longing", "anxiety",
              "seren", "rage", "anger", "angry", "wrath", "melanchol", "hope", "despair", "envy", "grateful",
              "resent", "lonely", "affection", "tenderness", "despise", "scorn",
              "disdain", "solitude", "lonely", "alone"], "Mental & Abstract"),
            (["math", "number", "calculat", "add", "subtract", "multiply", "divide",
              "geometry", "angle", "logic", "algorithm", "data", "variable",
              "function", "loop", "boolean"], "Mathematics & Computation"),
            (["body", "bone", "blood", "hand", "mouth", "eye", "ear", "lung",
              "heart", "skin", "nerve", "spine", "shoulder", "thigh", "ankle",
              "wrist", "brain", "skull", "jaw", "rib", "pelvis", "muscle", "tendon"],
             "Body Parts"),
            (["veil", "glamer", "essence", "vitality", "feeding pulse", "resonance"],
             "Cosmology & Reality"),
            (["heaven", "heavens", "cosmos", "reality", "universe"], "Cosmology & Reality"),
            (["home", "bed", "curtain", "window", "closet", "picture", "art",
              "wall", "comfort"], "Home & Comfort"),
            (["family", "parent", "child", "sibling", "mother", "father", "kid", "kin"],
             "Family & Kinship"),
            (["tech", "device", "ai", "machine", "screen", "wearable", "clock", "computer"],
             "Technology & Devices"),
            (["pleasure", "pain", "tease", "orgasm", "cum"], "Sexual & Explicit"),
            (["sex", "fuck", "cock", "pussy", "vagina", "penis", "clit", "ass", "tits", "oral"],
             "Sexual & Explicit"),
            (["vulgar", "shit", "piss", "whore", "slut", "cunt"], "Vulgar & Profane"),
            (["nature", "weather", "rain", "cloud", "star", "moon", "forest",
              "mountain", "valley", "water", "fire", "wind", "ice", "dust", "sand",
              "tree", "plant", "animal", "beast", "claw", "wing", "tail",
              "light", "glimmer", "glow", "shine", "spark", "color", "colour"],
             "Elements & Nature"),
            (["body", "eat", "drink", "sleep", "walk", "run", "bite", "see",
              "hear", "breathe"], "Beings & Creatures"),
            (["tool", "object", "weapon", "cloth", "wear", "vessel", "cord",
              "wheel", "shelter"], "Tools & Objects"),
            (["place", "time", "day", "night", "year", "hour", "home", "cave", "city"],
             "Place & Time"),
            (["facility", "facilities", "building", "room", "site"], "Place & Time"),
            (["quality", "big", "small", "good", "bad", "dark", "bright", "hot",
              "cold", "fast", "slow"], "Qualities"),
            (["social", "talk", "speak", "friend", "enemy", "respect", "insult",
              "command", "ask"], "Social & Communication"),
            (["activate", "activates", "move", "motion", "action", "act"], "Action & Motion"),
            (["abstract", "soul", "mind", "thought", "idea", "concept", "truth",
              "lie", "dream", "know", "remember"], "Mental & Abstract"),
            (["everyday", "want", "need", "go", "come", "make", "give", "take"],
             "Core Vocabulary"),
        ]

    def _resolve_category_name(self, category: str, existing: set) -> str:
        if category in existing:
            return category
        for existing_category in sorted(existing):
            if (
                category.lower() in existing_category.lower()
                or existing_category.lower() in category.lower()
            ):
                return existing_category
        return category

    def _category_guess_details(self, english: str, meaning: str) -> Dict:
        """Return a category hypothesis with confidence and matched evidence."""
        english_clean = english.lower().strip()
        text = f"{english_clean} {meaning.lower()}"
        existing = {
            row["category"]
            for row in self.conn.execute("SELECT DISTINCT category FROM roots").fetchall()
        }
        matches = []
        for keywords, category in self._category_rules():
            matched = [
                keyword for keyword in keywords
                if re.search(rf"(?<![a-z]){re.escape(keyword)}", text)
            ]
            if matched:
                resolved = self._resolve_category_name(category, existing)
                matches.append((resolved, matched))

        if not matches:
            return {
                "category": "Uncategorized",
                "confidence": "none",
                "reason": "no category keyword matched",
                "ambiguous": True,
            }

        first_category, first_keywords = matches[0]
        categories = list(dict.fromkeys(category for category, _keywords in matches))
        exact = any(
            english_clean == keyword or english_clean.rstrip("s") == keyword.rstrip("s")
            for keyword in first_keywords
        )
        if len(categories) > 1:
            return {
                "category": first_category,
                "confidence": "low",
                "reason": (
                    f"matched {', '.join(repr(k) for k in first_keywords[:3])}; "
                    f"also matched {', '.join(categories[1:])}"
                ),
                "ambiguous": True,
            }
        return {
            "category": first_category,
            "confidence": "high" if exact else "medium",
            "reason": f"matched {', '.join(repr(k) for k in first_keywords[:3])}",
            "ambiguous": False,
        }

    def _guess_category(self, english: str, meaning: str) -> str:
        """Pick the best existing category for a new root."""
        return self._category_guess_details(english, meaning)["category"]

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

    def auto_detect_compounds(self, limit: int = 50) -> list:
        """Try to auto-detect compound roots by matching known roots as prefixes/suffixes.
        Returns list of (compound, [components]) tuples."""
        all_roots = [r["root"] for r in self.conn.execute("SELECT root FROM roots ORDER BY LENGTH(root) DESC").fetchall()]
        simple_roots = [r for r in all_roots if len(r) <= 6]  # only match against short roots
        detected = []

        for compound in all_roots:
            if len(compound) <= 6:
                continue  # only try to decompose long roots
            # Try to split into known roots
            components = self._decompose(compound, simple_roots)
            if components and len(components) > 1:
                detected.append((compound, components))
                if len(detected) >= limit:
                    break

        return detected

    def _decompose(self, word: str, roots: list) -> list:
        """Try to decompose a word into a sequence of known roots."""
        if not word:
            return []
        for r in roots:
            if word.startswith(r) and len(r) >= 2:
                rest = word[len(r):]
                if not rest:
                    return [r]
                sub = self._decompose(rest, roots)
                if sub:
                    return [r] + sub
        return []

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

    def categorize(
        self,
        root: str = None,
        category: str = None,
        yes: bool = False,
        all_rows: bool = False,
        include_ambiguous: bool = False,
        limit: int = 20,
    ) -> Tuple[bool, str]:
        """Preview or apply guarded placeholder-category proposals."""
        proposals = self.category_proposals(root=root, category=category)
        lines = [
            "Xenari category cleanup",
            f"Matched placeholder rows: {len(proposals)}",
            "The limit controls display only; writes apply every eligible targeted row.",
        ]
        if root and not proposals:
            lines.append(f"No placeholder-category row found for root '{root}'.")
            return False, "\n".join(lines)

        eligible = []
        for proposal in proposals:
            changes = proposal["category"] != proposal["suggested_category"]
            ambiguous = proposal["ambiguous"] or proposal["confidence"] in {"low", "none"}
            if changes and (include_ambiguous or not ambiguous):
                eligible.append(proposal)

        shown = proposals[: max(limit, 0)]
        for proposal in shown:
            status = "ambiguous" if proposal["ambiguous"] else "eligible"
            if proposal["category"] == proposal["suggested_category"]:
                status = "no suggestion"
            lines.append(
                f"  - {proposal['root']}: {proposal['category']} -> {proposal['suggested_category']} "
                f"[{proposal['confidence']}, {status}] ({proposal['reason']})"
            )
        if len(proposals) > len(shown):
            lines.append(f"  ... {len(proposals) - len(shown)} more")
        lines.append(f"Eligible changes: {len(eligible)}")

        if not yes:
            lines.append("PREVIEW ONLY: no database write. Use --yes with --root, --category, or --all.")
            return True, "\n".join(lines)
        if not (root or category or all_rows):
            lines.append("Refusing broad write without --root, --category, or explicit --all.")
            return False, "\n".join(lines)
        if not eligible:
            lines.append("No eligible category changes to write.")
            return True, "\n".join(lines)

        backup_path = self._backup_before_mutation("categorize")
        with self.conn:
            for proposal in eligible:
                self.conn.execute(
                    "UPDATE roots SET category = ? WHERE root = ? AND category = ?",
                    (proposal["suggested_category"], proposal["root"], proposal["category"]),
                )
        lines.append(f"Backup: {backup_path}")
        lines.append(f"Wrote {len(eligible)} category change(s).")
        return True, "\n".join(lines)

    def migrate_from_markdown(self, md_path: Path):
        """Legacy one-time migration from an explicit archived markdown path.
        Only imports if the DB is empty."""
        md = Path(md_path)
        count = self.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0]
        if count > 0:
            print(f"DB already has {count} roots, skipping migration")
            return

        current_category = "Uncategorized"
        imported = 0
        mappings = 0

        with open(md, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Section header
                if line.startswith("## "):
                    current_category = line[3:].strip()
                    continue

                # Root row: | `root` | meaning | source |
                if line.startswith("| `") and not line.startswith("|---|"):
                    match = re.match(r"\| `([^`]+)` \| ([^|]+) \| ([^|]*) \|", line)
                    if not match:
                        match = re.match(r"\| `([^`]+)` \| ([^|]+) \|", line)
                    if match:
                        root = match.group(1).strip()
                        meaning = match.group(2).strip()
                        source = match.group(3).strip() if match.lastindex >= 3 else "lexicon"

                        try:
                            cur = self.conn.execute(
                                "INSERT INTO roots (root, meaning, category, source) VALUES (?, ?, ?, ?)",
                                (root, meaning, current_category, source)
                            )
                            root_id = cur.lastrowid

                            # Auto-map english keys from meaning words
                            short = meaning.lower().split("—")[0].strip()
                            for w in re.split(r"[ /,]+", short):
                                w = w.strip()
                                if w and len(w) > 1:
                                    self.conn.execute(
                                        "INSERT OR IGNORE INTO english_map (english_key, root_id) VALUES (?, ?)",
                                        (w, root_id)
                                    )
                                    mappings += 1

                            imported += 1
                        except sqlite3.IntegrityError:
                            pass  # duplicate root, skip

        # Manual overrides for common mismaps
        overrides = {
            "love": "zrent", "loved": "zrent",
            "big": "nyix",
            "daddy": "qli'xrontq", "dad": "qli'xrontq", "father": "qli'xrontq",
            "hate": "blun", "hated": "blun",
        }

        for eng, root in overrides.items():
            row = self.conn.execute("SELECT id FROM roots WHERE root = ?", (root,)).fetchone()
            if row:
                self.conn.execute(
                    "INSERT OR REPLACE INTO english_map (english_key, root_id) VALUES (?, ?)",
                    (eng, row["id"])
                )
                mappings += 1

        self.conn.commit()
        print(f"Migrated {imported} roots and {mappings} english mappings from {md}")
