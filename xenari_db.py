#!/usr/bin/env python3
"""
Xenari Database — sqlite source of truth for the Xenari conlang.

Schema:
  roots(id, root, meaning, category, source, timestamp, notes)
  english_map(id, english_key, root_id, context_note)

Usage:
  from xenari_db import XenariDB
  db = XenariDB()
  db.lookup("hate")
  db.add_root("hate", "blun", "to hate, detest", category="Mental & Abstract")
  db.search("feed")
  db.export_markdown(Path("xenari-lexicon-export.md"))
"""

import sqlite3
import re
import datetime
import hashlib
import shlex
from pathlib import Path
from typing import Optional, Dict, Tuple, List

DB_PATH = Path(__file__).parent / "xenari.db"


class XenariDB:
    def __init__(self, db_path: Optional[Path] = None, *, read_only: bool = False):
        """Open the canonical database.

        Read-only opens intentionally use SQLite's ``mode=ro`` and
        ``immutable=1`` URI flags.  Besides making the contract explicit, this
        prevents read commands from creating WAL/SHM sidecars or
        opportunistically initializing a schema.
        """
        self.db_path = Path(db_path or DB_PATH)
        self.read_only = read_only
        if read_only:
            uri = f"{self.db_path.resolve().as_uri()}?mode=ro&immutable=1"
            self.conn = sqlite3.connect(uri, uri=True)
        else:
            self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        if read_only:
            self.conn.execute("PRAGMA query_only=ON")
        if not read_only:
            # The canonical DB is version-controlled by itself; WAL sidecars
            # are ignored and can hide committed changes from export/commit
            # workflows.  Keep writes in the main DB file.
            self.conn.execute("PRAGMA journal_mode=DELETE")
            self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS roots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                root        TEXT UNIQUE NOT NULL,
                meaning     TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'Uncategorized',
                source      TEXT,
                timestamp   TEXT,
                notes       TEXT
            );

            CREATE TABLE IF NOT EXISTS english_map (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                english_key TEXT NOT NULL,
                root_id     INTEGER NOT NULL,
                context_note TEXT,
                FOREIGN KEY (root_id) REFERENCES roots(id) ON DELETE CASCADE,
                UNIQUE(english_key, root_id)
            );

            CREATE INDEX IF NOT EXISTS idx_english_key ON english_map(english_key);
            CREATE INDEX IF NOT EXISTS idx_root ON roots(root);
            CREATE INDEX IF NOT EXISTS idx_category ON roots(category);

            CREATE TABLE IF NOT EXISTS compounds (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                compound_root TEXT NOT NULL,
                component_root TEXT NOT NULL,
                position    INTEGER NOT NULL,
                FOREIGN KEY (compound_root) REFERENCES roots(root) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_compound ON compounds(compound_root);
            CREATE INDEX IF NOT EXISTS idx_component ON compounds(component_root);

            CREATE TABLE IF NOT EXISTS semantic_relations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                root_a      TEXT NOT NULL,
                root_b      TEXT NOT NULL,
                relation    TEXT NOT NULL,
                notes       TEXT,
                UNIQUE(root_a, root_b, relation)
            );

            CREATE INDEX IF NOT EXISTS idx_rel_a ON semantic_relations(root_a);
            CREATE INDEX IF NOT EXISTS idx_rel_b ON semantic_relations(root_b);

            CREATE TABLE IF NOT EXISTS tool_meta (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
        """)
        self.conn.execute(
            """INSERT OR IGNORE INTO tool_meta (key, value, updated_at)
               VALUES (?, ?, ?)""",
            ("schema_version", "2026-07-09.2", datetime.datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _auto_export(self):
        """Deprecated: exports must be explicit so repo/site/live stay in sync."""
        return

    # ─── Core lookups ───────────────────────────────────────────

    def lookup(self, english: str) -> Optional[Tuple[str, str]]:
        """english word → (root, meaning)"""
        key = english.lower().strip()
        rows = self.conn.execute(
            """SELECT r.root, r.meaning, e.context_note FROM english_map e
               JOIN roots r ON r.id = e.root_id
               WHERE e.english_key = ?""", (key,)
        ).fetchall()
        if not rows:
            return None
        row = max(rows, key=lambda r: self._lookup_score(key, r["meaning"], r["context_note"]))
        return (row["root"], row["meaning"]) if row else None

    def _lookup_score(self, key: str, meaning: str, context_note: str = None) -> int:
        head = self._audit_headword(meaning)
        note = (context_note or "").lower()
        note_tokens = [token for token in re.split(r"[ /,;:-]+", note) if token]
        if key in note_tokens or any(len(token) >= 3 and key.startswith(token) for token in note_tokens):
            return 5
        if head == key:
            return 4
        if head.startswith(key + " "):
            return 3
        if key in re.split(r"[ /,;]+", head):
            return 2
        return 1

    def lookup_root(self, root: str) -> Optional[Dict]:
        """root → full row"""
        row = self.conn.execute("SELECT * FROM roots WHERE root = ?", (root,)).fetchone()
        return dict(row) if row else None

    def has_english(self, key: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM english_map WHERE english_key = ?",
            (key.lower().strip(),)
        ).fetchone() is not None

    def has_root(self, root: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM roots WHERE root = ?", (root,)
        ).fetchone() is not None

    # ─── Stats ──────────────────────────────────────────────────

    def stats(self) -> str:
        roots = self.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0]
        maps = self.conn.execute("SELECT COUNT(*) FROM english_map").fetchone()[0]
        cats = self.conn.execute("SELECT COUNT(DISTINCT category) FROM roots").fetchone()[0]
        return f"Roots: {roots} | English mappings: {maps} | Categories: {cats}"

    # ─── Search ─────────────────────────────────────────────────

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Ranked search across roots, meanings, and english keys."""
        clean = query.lower().strip()
        q = f"%{clean}%"
        rows = self.conn.execute(
            """SELECT DISTINCT r.root, r.meaning, r.category,
                      GROUP_CONCAT(e.english_key, ', ') as english_keys
               FROM roots r
               LEFT JOIN english_map e ON e.root_id = r.id
               WHERE r.root LIKE ? OR r.meaning LIKE ? OR e.english_key LIKE ?
               GROUP BY r.id""", (q, q, q)
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            keys = [k.strip().lower() for k in (item.get("english_keys") or "").split(",") if k.strip()]
            root = item["root"].lower()
            meaning = item["meaning"].lower()
            head = self._audit_headword(item["meaning"])
            score = 0
            if clean in keys:
                score += 100
            if head == clean:
                score += 85
            if root == clean:
                score += 80
            if any(k.startswith(clean) for k in keys):
                score += 55
            if head.startswith(clean):
                score += 45
            if root.startswith(clean):
                score += 40
            if clean in meaning:
                score += 20
            if clean in root:
                score += 15
            item["score"] = score
            results.append(item)
        results.sort(key=lambda r: (-r["score"], len(r["root"]), r["root"]))
        return results[:limit]

    def _root_shape_score(self, root: str) -> int:
        """Score pronounceable root shapes for proposal ordering."""
        score = 100
        if 4 <= len(root) <= 5:
            score += 24
        elif len(root) == 3:
            score += 10
        elif len(root) == 6:
            score += 2
        else:
            score -= 18
        if "'" in root:
            score -= 10
        if re.search(r"[bcdfghjklmnpqrstvwxyz]{4,}", root):
            score -= 35
        if re.search(r"[bcdfghjklmnpqrstvwxyz]{3,}", root):
            score -= 18
        if re.search(r"([bcdfghjklmnpqrstvwxyz])\1", root):
            score -= 26
        if re.search(r"(kg|gk|cs|zs|sx|xq|qx|qg|gq|td|dt|bp|pb)", root):
            score -= 12
        if re.search(r"(kgl|glf|ngkr|nqk|mpq|ntq)", root):
            score -= 35
        if re.search(r"[aeiou]{2,}", root):
            score -= 12
        if root[0] in "qx":
            score -= 3
        if root in {"ra", "ka", "ta", "na", "fa", "mo", "vi", "nu", "sa", "lo", "ve", "du", "pe", "ko", "xa", "xe", "xi", "xo", "zu", "po", "ha", "va"}:
            score -= 80
        if root[-1] in "aeou":
            score += 4
        if re.fullmatch(r"[bcdfghjklmnpqrstvwxyz]?[aeou][bcdfghjklmnpqrstvwxyz][aeou]?", root):
            score += 8
        if re.fullmatch(r"[bcdfghjklmnpqrstvwxyz]{1,2}[aeou][bcdfghjklmnpqrstvwxyz]{1,2}[aeou]", root):
            score += 8
        return score

    def propose_root(self, english: str, meaning: str = "", limit: int = 8) -> List[Dict]:
        """Suggest unused root shapes and include safety notes for each."""
        key = english.lower().strip()
        gloss = meaning.strip() or key
        seed = hashlib.sha256(f"{key}|{gloss}".encode("utf-8")).hexdigest()
        vowels = "aeou"
        onsets = ["p", "t", "k", "q", "f", "s", "z", "c", "x", "h", "m", "n", "r", "l", "y",
                  "pr", "tr", "kr", "fr", "sr", "zr", "cr", "xr", "qr", "ml", "gl", "br", "dr"]
        codas = ["p", "t", "k", "q", "f", "s", "z", "c", "x", "m", "n", "r", "l", "mp", "nt", "ngk", "nq", ""]
        seen = set()
        candidates = []
        idx = 0
        existing = self.conn.execute("SELECT root, meaning FROM roots").fetchall()
        english_bits = set(re.findall(r"[a-z]{3,}", key + " " + gloss))

        while len(candidates) < max(limit * 6, 40) and idx < 900:
            chunk = seed[idx % len(seed):] + seed[:idx % len(seed)]
            a = int(chunk[:2], 16)
            b = int(chunk[2:4], 16)
            c = int(chunk[4:6], 16)
            d = int(chunk[6:8], 16)
            pattern = idx % 4
            if pattern == 0:
                root = onsets[a % len(onsets)] + vowels[b % len(vowels)] + codas[c % len(codas)]
            elif pattern == 1:
                root = onsets[a % len(onsets)] + vowels[b % len(vowels)] + codas[c % len(codas)] + vowels[d % len(vowels)]
            elif pattern == 2:
                root = onsets[a % len(onsets)] + vowels[b % len(vowels)] + onsets[c % len(onsets)] + vowels[d % len(vowels)]
            else:
                root = onsets[a % len(onsets)] + vowels[b % len(vowels)] + codas[c % len(codas)] + onsets[d % len(onsets)] + vowels[(a + d) % len(vowels)]
            idx += 1

            if root in seen or self.has_root(root):
                continue
            seen.add(root)
            issues = self.validate_phonotactics(root)
            if issues:
                continue

            near = []
            for row in existing:
                dist = self._edit_distance(root, row["root"])
                if 0 < dist <= 2:
                    near.append(f"{row['root']} ({row['meaning']})")
                if len(near) >= 3:
                    break

            notes = []
            score = self._root_shape_score(root)
            if re.search(r"([bcdfghjklmnpqrstvwxyz])\1", root):
                notes.append("style: repeated consonant")
            if re.search(r"[bcdfghjklmnpqrstvwxyz]{3,}", root) or re.search(r"(kgl|glf|ngkr|nqk|mpq|ntq)", root):
                notes.append("style: crunchy cluster")
            if near:
                notes.append("near: " + "; ".join(near))
                score -= 30 + (10 * len(near))
            if any(bit in root or root in bit for bit in english_bits):
                notes.append("englishy/cognate smell")
                score -= 35
            if not notes:
                notes.append("clean")
                score += 20

            candidates.append({
                "root": root,
                "meaning": gloss,
                "category": self._guess_category(key, gloss),
                "notes": notes,
                "score": score,
            })
        candidates.sort(key=lambda item: (-item["score"], len(item["root"]), item["root"]))
        return candidates[:limit]

    def search_category(self, category: str) -> List[Dict]:
        """Get all roots in a category."""
        rows = self.conn.execute(
            "SELECT * FROM roots WHERE category LIKE ? ORDER BY root",
            (f"%{category}%",)
        ).fetchall()
        return [dict(r) for r in rows]

    def categories(self) -> List[Tuple[str, int]]:
        """List all categories with root counts."""
        rows = self.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM roots GROUP BY category ORDER BY cnt DESC"
        ).fetchall()
        return [(r["category"], r["cnt"]) for r in rows]

    # ─── Add / Remove ───────────────────────────────────────────

    def _edit_distance(self, a: str, b: str) -> int:
        if len(a) < len(b):
            a, b = b, a
        if len(b) == 0:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
            prev = curr
        return prev[-1]

    def _stem(self, word: str) -> str:
        w = word.lower().strip()
        for suffix in ["ing", "edly", "ingly", "ed", "es", "ly", "er", "est", "ness", "ment", "s"]:
            if w.endswith(suffix) and len(w) > len(suffix) + 2:
                return w[:-len(suffix)]
        return w

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

    # ─── Category helpers ───────────────────────────────────────

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

    # ─── Compounds ─────────────────────────────────────────────

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

    # ─── Semantic Relations ─────────────────────────────────────

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

    def near_meanings(self, query: str, limit: int = 12) -> List[Dict]:
        """Return ranked near matches for a proposed English meaning."""
        return self.search(query, limit=limit)

    def metadata_report(self) -> str:
        rows = self.conn.execute("SELECT key, value, updated_at FROM tool_meta ORDER BY key").fetchall()
        lines = ["Xenari metadata", f"DB path: {self.db_path}", self.stats()]
        if not rows:
            lines.append("tool_meta: empty")
            return "\n".join(lines)
        for row in rows:
            lines.append(f"{row['key']}: {row['value']} ({row['updated_at']})")
        return "\n".join(lines)

    def lint(self, limit: int = 40) -> str:
        """Heuristic lint for suspicious but not automatically wrong entries."""
        rows = [dict(r) for r in self.conn.execute(
            "SELECT root, meaning, category, source, notes FROM roots ORDER BY root"
        ).fetchall()]
        phrasey = []
        englishy = []
        stale_category = []
        orphan_relations = []

        english_words = {
            "love", "hate", "danger", "alien", "figure", "lake", "mother", "father",
            "computer", "byte", "file", "music", "window", "clock", "human",
        }
        for row in rows:
            meaning = row["meaning"].strip()
            head = self._audit_headword(meaning)
            if len(head.split()) > 6 or re.search(r"[.!?]", meaning):
                phrasey.append(row)
            if any(word in row["root"].lower() and len(row["root"]) > len(word) for word in english_words):
                englishy.append(row)
            if row["category"] in {"Uncategorized", "New Roots (added via tool)"}:
                stale_category.append(row)

        for rel in self.conn.execute("SELECT root_a, root_b, relation FROM semantic_relations ORDER BY root_a, root_b").fetchall():
            missing = [r for r in (rel["root_a"], rel["root_b"]) if not self.has_root(r)]
            if missing:
                orphan_relations.append((dict(rel), missing))

        lines = [
            "Xenari lint",
            f"Phrase-like definitions: {len(phrasey)}",
            f"Englishy-looking roots: {len(englishy)}",
            f"Stale/placeholder categories: {len(stale_category)}",
            f"Orphan semantic relations: {len(orphan_relations)}",
        ]

        def rows_section(title: str, items: list) -> None:
            lines.extend(["", title])
            if not items:
                lines.append("  none")
                return
            for item in items[:limit]:
                lines.append(f"  - {item['root']}[{item['category']}]: {item['meaning']}")
            if len(items) > limit:
                lines.append(f"  ... {len(items) - limit} more")

        rows_section("Phrase-like definitions", phrasey)
        rows_section("Englishy-looking roots", englishy)
        rows_section("Stale/placeholder categories", stale_category)
        lines.extend(["", "Orphan semantic relations"])
        if not orphan_relations:
            lines.append("  none")
        for rel, missing in orphan_relations[:limit]:
            lines.append(f"  - {rel['root_a']} {rel['relation']} {rel['root_b']} (missing: {', '.join(missing)})")
        lines.extend([
            "",
            "Suggested next commands",
            "  python3 xenari_tool.py inspect <root>",
            "  python3 xenari_tool.py coin <english> <meaning>",
            "  python3 xenari_tool.py categories",
        ])
        return "\n".join(lines)

    def _curation_rows(self) -> list:
        return [dict(row) for row in self.conn.execute(
            """SELECT root, meaning, category, source, notes
               FROM roots
               ORDER BY category, root"""
        ).fetchall()]

    def category_proposals(self, root: str = None, category: str = None) -> list:
        """Return placeholder-category hypotheses without changing the database."""
        proposals = []
        for row in self._curation_rows():
            if row["category"] not in {"Uncategorized", "New Roots (added via tool)"}:
                continue
            if root and row["root"] != root:
                continue
            if category and row["category"] != category:
                continue
            head = self._audit_headword(row["meaning"])
            english_hint = head or row["meaning"]
            quoted = re.search(r"English '([^']+)'", row["meaning"], re.I)
            if quoted:
                english_hint = quoted.group(1)
            details = self._category_guess_details(english_hint, row["meaning"])
            proposals.append({
                **row,
                "suggested_category": details["category"],
                "confidence": details["confidence"],
                "reason": details["reason"],
                "ambiguous": details["ambiguous"],
            })
        proposals.sort(key=lambda proposal: (proposal["suggested_category"], proposal["root"]))
        return proposals

    def phrase_definition_candidates(self) -> list:
        candidates = []
        for row in self._curation_rows():
            head = self._audit_headword(row["meaning"])
            if len(head.split()) > 6 or re.search(r"[.!?]", row["meaning"]):
                candidates.append(row)
        return candidates

    def _relation_candidate_kind(self, head: str, group: list) -> Dict:
        texts = [self._audit_normalize(row["meaning"]) for row in group]
        categories = {row["category"].lower() for row in group}
        combined = " ".join(
            str(row.get(field) or "").lower()
            for row in group
            for field in ("meaning", "source", "notes", "category")
        )
        register_words = {
            "archaic", "casual", "colloquial", "formal", "poetic", "slang",
            "technical", "vulgar", "profane", "honorific", "register",
        }
        register_hits = sorted(word for word in register_words if word in combined)
        if register_hits:
            return {
                "kind": "possible register variant",
                "confidence": "medium",
                "reason": f"shared headword with register marker(s): {', '.join(register_hits)}",
                "relation": "register_variant",
            }
        if len(set(texts)) == 1:
            if len(categories) > 1:
                return {
                    "kind": "possible category clash",
                    "confidence": "high",
                    "reason": "identical normalized definition appears in different categories",
                    "relation": None,
                }
            return {
                "kind": "possible synonym",
                "confidence": "high",
                "reason": "identical normalized definition in the same category",
                "relation": "synonym",
            }
        qualifier_tokens = [set(text.split()) - set(head.split()) for text in texts]
        overlap = set.intersection(*qualifier_tokens) if qualifier_tokens else set()
        overlap -= {"a", "an", "and", "as", "of", "or", "the", "to"}
        if len(categories) > 1 and overlap:
            return {
                "kind": "possible category clash",
                "confidence": "medium",
                "reason": "shared headword/qualifier but different categories",
                "relation": None,
            }
        return {
            "kind": "possible false friend",
            "confidence": "medium",
            "reason": "shared English headword but distinct qualifiers or category context",
            "relation": None,
        }

    def relation_candidates(self) -> list:
        """Return classified duplicate-headword hypotheses for human review."""
        by_head = {}
        for row in self._curation_rows():
            head = self._audit_headword(row["meaning"])
            if head:
                by_head.setdefault(head, []).append(row)
        candidates = []
        for head, group in by_head.items():
            if len(group) < 2:
                continue
            roots = sorted({row["root"] for row in group})
            placeholders = ",".join("?" for _ in roots)
            linked = self.conn.execute(
                f"""SELECT 1 FROM semantic_relations
                    WHERE root_a IN ({placeholders}) AND root_b IN ({placeholders})
                    LIMIT 1""",
                tuple(roots) + tuple(roots),
            ).fetchone()
            if linked:
                continue
            candidates.append({
                "head": head,
                "rows": group,
                **self._relation_candidate_kind(head, group),
            })
        priority = {
            "possible synonym": 0,
            "possible register variant": 1,
            "possible category clash": 2,
            "possible false friend": 3,
        }
        candidates.sort(key=lambda item: (priority[item["kind"]], item["head"]))
        return candidates

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

    def curation_report(
        self,
        limit: int = 30,
        placeholder: bool = True,
        phrases: bool = True,
        relations: bool = True,
    ) -> str:
        """Human-review curation queue for categories, definitions, and relation gaps."""
        placeholder_categories = self.category_proposals()
        phrase_definitions = self.phrase_definition_candidates()
        relation_candidates = self.relation_candidates()

        lines = [
            "Xenari curation report",
            f"Placeholder category rows: {len(placeholder_categories)}",
            f"Phrase-like definitions: {len(phrase_definitions)}",
            f"Unlinked duplicate-headword relation candidates: {len(relation_candidates)}",
        ]

        if placeholder:
            lines.extend(["", "Placeholder category suggestions (grouped by suggestion)"])
            visible = placeholder_categories[: max(limit, 0)]
            grouped = {}
            for proposal in visible:
                grouped.setdefault(proposal["suggested_category"], []).append(proposal)
            if not grouped:
                lines.append("  none")
            for suggested in sorted(grouped):
                lines.append(f"  {suggested}:")
                for proposal in grouped[suggested]:
                    lines.append(
                        f"    - {proposal['root']}: {proposal['meaning']} "
                        f"[{proposal['confidence']}] ({proposal['reason']})"
                    )
            if len(placeholder_categories) > len(visible):
                lines.append(f"  ... {len(placeholder_categories) - len(visible)} more")

        if phrases:
            lines.extend(["", "Phrase-like definition review"])
            if not phrase_definitions:
                lines.append("  none")
            for row in phrase_definitions[:limit]:
                lines.append(f"  - {row['root']}[{row['category']}]: {row['meaning']}")
            if len(phrase_definitions) > limit:
                lines.append(f"  ... {len(phrase_definitions) - limit} more")

        if relations:
            lines.extend(["", "Relation candidate groups (hypotheses, not facts)"])
            if not relation_candidates:
                lines.append("  none")
            for candidate in relation_candidates[:limit]:
                joined = "; ".join(
                    f"{row['root']}[{row['category']}]: {row['meaning']}"
                    for row in candidate["rows"][:6]
                )
                lines.append(
                    f"  - {candidate['head']} [{candidate['kind']}, "
                    f"confidence={candidate['confidence']}]: {candidate['reason']}"
                )
                lines.append(f"    {joined}")
                if candidate["relation"] and len(candidate["rows"]) == 2:
                    root_a, root_b = (row["root"] for row in candidate["rows"])
                    lines.append(
                        "    preview only: python3 xenari_tool.py relate "
                        f"{shlex.quote(root_a)} {shlex.quote(root_b)} "
                        f"--relation {candidate['relation']} --dry-run"
                    )
                else:
                    roots = " ".join(row["root"] for row in candidate["rows"][:3])
                    lines.append(f"    review first: {roots}")
            if len(relation_candidates) > limit:
                lines.append(f"  ... {len(relation_candidates) - limit} more")

        lines.extend([
            "",
            "Suggested next commands",
            "  python3 xenari_tool.py categorize --root <root>",
            "  python3 xenari_tool.py inspect <root>",
            "  python3 xenari_tool.py relations <root>",
            "  python3 xenari_tool.py search <headword>",
        ])
        return "\n".join(lines)

    def get_synonyms(self, root: str) -> list:
        """Get synonym roots."""
        rows = self.conn.execute(
            "SELECT root_b FROM semantic_relations WHERE root_a = ? AND relation = 'synonym' UNION SELECT root_a FROM semantic_relations WHERE root_b = ? AND relation = 'synonym'",
            (root, root)
        ).fetchall()
        return [r[0] for r in rows]

    # ─── Export ─────────────────────────────────────────────────

    def export_markdown(self, path: Path) -> str:
        """Generate a clean markdown lexicon from the DB at an explicit path."""
        out_path = Path(path)
        cats = self.categories()

        lines = [
            "# XENARI — Full Dictionary",
            "",
            f"**Total roots:** {sum(c for _, c in cats)}",
            f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
        ]

        for cat_name, count in cats:
            lines.append(f"## {cat_name}")
            lines.append("")
            lines.append("| Root | Meaning | Source |")
            lines.append("|---|---|---|")
            rows = self.conn.execute(
                "SELECT root, meaning, source FROM roots WHERE category = ? ORDER BY root",
                (cat_name,)
            ).fetchall()
            for r in rows:
                src = r["source"] or ""
                lines.append(f"| `{r['root']}` | {r['meaning']} | {src} |")
            lines.append("")

        content = "\n".join(lines)
        out_path.write_text(content, encoding="utf-8")
        return content

    def export_json(self) -> str:
        """Export everything as JSON."""
        import json
        roots = []
        for r in self.conn.execute("SELECT * FROM roots ORDER BY category, root").fetchall():
            row = dict(r)
            keys = self.conn.execute(
                "SELECT english_key FROM english_map WHERE root_id = ?", (r["id"],)
            ).fetchall()
            row["english_keys"] = [k["english_key"] for k in keys]
            roots.append(row)
        return json.dumps(roots, ensure_ascii=False, indent=2)

    # ─── Audit ──────────────────────────────────────────────────

    def _audit_normalize(self, text: str) -> str:
        text = (text or "").lower().strip().replace("—", "-")
        text = re.sub(r"\([^)]*\)", "", text)
        text = re.sub(r"`[^`]*`", "", text)
        text = re.sub(r"\b(already exists|already coined above)\b", "", text)
        text = re.sub(r"[^a-z0-9!' ]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _audit_headword(self, meaning: str) -> str:
        head = (meaning or "").lower().strip().replace("—", "-")
        head = re.sub(r"\([^)]*\)", "", head)
        head = re.sub(r"`[^`]*`", "", head)
        head = re.split(r"\s+-\s+|;|:|,", head)[0]
        head = self._audit_normalize(head)
        head = head.strip(" \"")
        head = re.sub(r"^(to|a|an|the)\s+", "", head)
        return re.sub(r"\s+", " ", head).strip()

    def audit(self, limit: int = 40) -> str:
        """Read-only lexicon audit for duplicates, stale markers, and validator failures."""
        roots = [dict(r) for r in self.conn.execute(
            "SELECT id, root, meaning, category, source, notes FROM roots ORDER BY root"
        ).fetchall()]
        maps = [dict(r) for r in self.conn.execute(
            """SELECT e.english_key, r.root, r.meaning, r.category
               FROM english_map e JOIN roots r ON r.id = e.root_id
               ORDER BY e.english_key, r.root"""
        ).fetchall()]

        root_counts = {}
        lower_root_counts = {}
        exact = {}
        headwords = {}
        markers = []
        phon_failures = []
        english_keys = {}

        for row in roots:
            root = row["root"]
            root_counts[root] = root_counts.get(root, 0) + 1
            lower = root.lower()
            lower_root_counts[lower] = lower_root_counts.get(lower, 0) + 1

            norm = self._audit_normalize(row["meaning"])
            if norm:
                exact.setdefault(norm, []).append(row)

            head = self._audit_headword(row["meaning"])
            if head:
                headwords.setdefault(head, []).append(row)

            text = " ".join(str(row.get(k) or "") for k in ("meaning", "source", "notes"))
            if (
                re.search(r"\b(reanalyzed|obsolete|deprecated|duplicate|duplicates)\b", text, re.I)
                or "CONFLICT" in text
                or "already =" in text
            ):
                markers.append(row)

            issues = self.validate_phonotactics(root)
            if issues:
                phon_failures.append((row, issues))

        for row in maps:
            english_keys.setdefault(row["english_key"].lower(), set()).add(row["root"])

        duplicate_roots = [r for r, count in root_counts.items() if count > 1]
        duplicate_lower_roots = [r for r, count in lower_root_counts.items() if count > 1]
        exact_dupes = [(k, v) for k, v in exact.items() if len(v) > 1]
        headword_dupes = [(k, v) for k, v in headwords.items() if len(v) > 1]
        english_collisions = [(k, v) for k, v in english_keys.items() if len(v) > 1]
        actionable_exact_dupes = []
        for key, rows_for_key in exact_dupes:
            texts = " ".join(
                " ".join(str(r.get(field) or "") for field in ("meaning", "source", "notes"))
                for r in rows_for_key
            )
            has_stale_marker = (
                re.search(r"\b(reanalyzed|obsolete|deprecated|duplicate|duplicates)\b", texts, re.I)
                or "CONFLICT" in texts
                or re.search(r"\bno\.|new root|already =", texts, re.I)
            )
            sources = [r.get("source") or "" for r in rows_for_key]
            has_generated_over_canon = any(s.endswith("_gap_fill") for s in sources) and any(
                not s.endswith("_gap_fill") for s in sources
            )
            if has_stale_marker or has_generated_over_canon:
                actionable_exact_dupes.append((key, rows_for_key))

        exact_dupes.sort(key=lambda item: (-len(item[1]), item[0]))
        headword_dupes.sort(key=lambda item: (-len(item[1]), item[0]))
        actionable_exact_dupes.sort(key=lambda item: (-len(item[1]), item[0]))

        lines = [
            "Xenari audit",
            f"Roots: {len(roots)}",
            f"English mappings: {len(maps)}",
            f"Duplicate exact roots: {len(duplicate_roots)}",
            f"Duplicate lowercase roots: {len(duplicate_lower_roots)}",
            f"English keys mapped to multiple roots: {len(english_collisions)}",
            f"Actionable exact duplicate groups: {len(actionable_exact_dupes)}",
            f"Raw exact meaning duplicate groups: {len(exact_dupes)}",
            f"Raw headword duplicate groups: {len(headword_dupes)}",
            f"Stale/conflict/reanalysis marker rows: {len(markers)}",
            f"Phonotactic validator failures: {len(phon_failures)}",
            "",
            "Note: english-key collisions are noisy because english_map indexes words inside definitions.",
            "Note: raw duplicate groups include synonyms, register variants, particles, and derived families.",
        ]

        def fmt_group(title: str, groups: list) -> None:
            lines.extend(["", title])
            if not groups:
                lines.append("  none")
                return
            for key, rows_for_key in groups[:limit]:
                roots_for_key = "; ".join(
                    f"{r['root']}[{r['category']}]: {r['meaning']}" for r in rows_for_key
                )
                lines.append(f"  - {key} ({len(rows_for_key)}): {roots_for_key}")

        fmt_group("Actionable exact duplicates", actionable_exact_dupes)
        fmt_group("Raw exact meaning duplicates", exact_dupes)
        fmt_group("Headword duplicates", headword_dupes)

        lines.extend(["", "Marker rows"])
        if not markers:
            lines.append("  none")
        for row in markers[:limit]:
            lines.append(f"  - {row['root']}[{row['category']}]: {row['meaning']}")

        lines.extend(["", "Phonotactic failures"])
        if not phon_failures:
            lines.append("  none")
        for row, issues in phon_failures[:limit]:
            lines.append(f"  - {row['root']}[{row['category']}]: {'; '.join(issues)}")

        return "\n".join(lines)

    # ─── Migration from markdown ────────────────────────────────

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
    def validate_phonotactics(self, root: str) -> list:
        """Validate a root against xenari phonotactic rules.
        Returns list of issues (empty = valid)."""
        issues = []
        vowels = set("aeiou")
        valid_consonants = set("pbtdkgq'fszcxhmnrly")
        # v is a morphology marker (vi=animate, nu=inanimate, vu=passive) not a native consonant
        # but it appears in many compound roots as a suffix, so we allow it
        valid_compound_markers = set("v")
        # digraphs: ny, ng
        valid_codas = {"mp", "nt", "ngk", "nq"}
        valid_onset_clusters = {"pr","tr","kr","gr","fr","sr","zr","cr","xr","qr","mr",
                                 "pl","tl","kl","gl","fl","sl","cl","xl","ql","ml",
                                 "br","dr","bl","dl"}
        
        if not root:
            issues.append("empty root")
            return issues

        if not any(c in vowels for c in root):
            issues.append("root must contain at least one vowel")
        
        # Glottal stop cannot appear word-initially
        if root.startswith("'"):
            issues.append("glottal stop cannot be word-initial")
        
        # q cannot be followed by i in the same syllable
        for i in range(len(root) - 1):
            if root[i] == 'q' and root[i+1] == 'i':
                issues.append("q followed by i (uvular + high front disallowed)")
        
        # No gemination (doubled consonants) inside a simple root.
        # Longer lexicalized compounds often create doubled consonants at morpheme
        # boundaries (qont + toq -> qonttoq), so only short/simple forms are
        # flagged here. xx remains broadly tolerated as a common compound seam.
        for i in range(len(root) - 1):
            c = root[i]
            if c == root[i+1] and c not in vowels:
                if c == 'x' or len(root) > 5:
                    continue  # tolerated in compounds
                issues.append(f"gemination: {c}{c} at position {i}")
        
        # Every multisyllabic root must have at least one closed syllable
        # Count vowel groups (syllable nuclei)
        vowel_groups = []
        i = 0
        while i < len(root):
            if root[i] in vowels:
                start = i
                while i < len(root) and root[i] in vowels:
                    i += 1
                vowel_groups.append((start, i))
            else:
                i += 1
        
        if len(vowel_groups) >= 2:
            # Check if there's at least one consonant after a vowel group before the next one
            has_closed = False
            for j in range(len(vowel_groups) - 1):
                end_of_vg = vowel_groups[j][1]
                start_of_next = vowel_groups[j+1][0]
                if end_of_vg < start_of_next:
                    has_closed = True
                    break
            # Also check if last vowel group is followed by a consonant
            if vowel_groups[-1][1] < len(root):
                has_closed = True
            if not has_closed:
                issues.append("multisyllabic root with no closed syllable")
        
        # Check for vowel hiatus (adjacent vowels across syllable boundary)
        for i in range(len(root) - 1):
            if root[i] in vowels and root[i+1] in vowels:
                issues.append(f"vowel hiatus: {root[i]}{root[i+1]} at position {i}")
        
        # Check for invalid characters
        for i, c in enumerate(root):
            if c not in vowels and c not in valid_consonants and c not in valid_compound_markers and c != "'":
                issues.append(f"invalid character '{c}' at position {i}")
        
        return issues
