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
  db.export_markdown()
"""

import sqlite3
import re
import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, List

DB_PATH = Path(__file__).parent / "xenari.db"
LEXICON_MD = Path(__file__).parent / "xenari-lexicon.md"


class XenariDB:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
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
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _auto_export(self):
        """Auto-export JSON to nyx-site after DB changes."""
        try:
            import json as _json
            json_str = self.export_json()
            path = Path("/home/computment/nyx-site/src/data/xenari-dict.json")
            path.write_text(json_str, encoding="utf-8")
        except Exception:
            pass  # don't fail the add/remove if export fails

    # ─── Core lookups ───────────────────────────────────────────

    def lookup(self, english: str) -> Optional[Tuple[str, str]]:
        """english word → (root, meaning)"""
        row = self.conn.execute(
            """SELECT r.root, r.meaning FROM english_map e
               JOIN roots r ON r.id = e.root_id
               WHERE e.english_key = ?""", (english.lower().strip(),)
        ).fetchone()
        return (row["root"], row["meaning"]) if row else None

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
        """Fuzzy search across roots, meanings, and english keys."""
        q = f"%{query.lower()}%"
        rows = self.conn.execute(
            """SELECT DISTINCT r.root, r.meaning, r.category,
                      GROUP_CONCAT(e.english_key, ', ') as english_keys
               FROM roots r
               LEFT JOIN english_map e ON e.root_id = r.id
               WHERE r.root LIKE ? OR r.meaning LIKE ? OR e.english_key LIKE ?
               GROUP BY r.id
               LIMIT ?""", (q, q, q, limit)
        ).fetchall()
        return [dict(r) for r in rows]

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
                 extra_english_keys: List[str] = None) -> Tuple[bool, List[str]]:
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

        # Phonotactic validation
        phon_issues = self.validate_phonotactics(root)
        for pi in phon_issues:
            msgs.append(f"Phonotactic warning: {pi}")

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
        self.conn.execute("DELETE FROM english_map WHERE root_id = ?", (row["id"],))
        self.conn.execute("DELETE FROM roots WHERE id = ?", (row["id"],))
        self.conn.commit()
        print(f"Removed: {root} ({row['meaning']})")
        return True

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

    def _guess_category(self, english: str, meaning: str) -> str:
        """Pick the best existing category for a new root."""
        text = (english + " " + meaning).lower()

        # Get existing categories from DB
        existing_cats = [r["category"] for r in self.conn.execute(
            "SELECT DISTINCT category FROM roots"
        ).fetchall()]

        rules = [
            (["succubus", "feed", "brat", "horny", "goth", "kinky", "lewd", "submit",
              "dominant", "shameless", "needy", "clingy", "roleplay", "prad", "strem",
              "ngal", "zhrek", "ngrok", "zhem", "smek", "frez", "mben", "svet", "mrok"],
             "Succubus Culture & Feeding"),
            (["overfeed", "pathology", "fast soul"], "Succubus Culture & Feeding"),
            (["cooking", "kitchen", "boil", "fry", "bake", "chop", "stir", "spice",
              "recipe", "ingredient", "meal", "snack", "taste", "simmer", "grill"],
             "Plants & Food"),
            (["music", "sing", "song", "drum", "flute", "instrument", "rhythm",
              "melody", "beat", "harmony", "chorus"], "Arts & Culture"),
            (["hate", "jealous", "grief", "nostalgia", "contempt", "awe", "bored",
              "excit", "disappoint", "shame", "pride", "guilt", "longing", "anxiety",
              "seren", "rage", "melanchol", "hope", "despair", "envy", "grateful",
              "resent", "lonely", "affection", "tenderness", "despise", "scorn",
              "disdain"], "Mental & Abstract"),
            (["math", "number", "calculat", "add", "subtract", "multiply", "divide",
              "geometry", "angle", "logic", "algorithm", "data", "variable",
              "function", "loop", "boolean"], "Mathematics & Computation"),
            (["body", "bone", "blood", "hand", "mouth", "eye", "ear", "lung",
              "heart", "skin", "nerve", "spine", "shoulder", "thigh", "ankle",
              "wrist", "brain", "skull", "jaw", "rib", "pelvis", "muscle", "tendon"],
             "Body Parts"),
            (["veil", "glamer", "essence", "vitality", "feeding pulse", "resonance"],
             "Cosmology & Reality"),
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
              "tree", "plant", "animal", "beast", "claw", "wing", "tail"],
             "Elements & Nature"),
            (["body", "eat", "drink", "sleep", "walk", "run", "bite", "see",
              "hear", "breathe"], "Beings & Creatures"),
            (["tool", "object", "weapon", "cloth", "wear", "vessel", "cord",
              "wheel", "shelter"], "Tools & Objects"),
            (["place", "time", "day", "night", "year", "hour", "home", "cave", "city"],
             "Place & Time"),
            (["quality", "big", "small", "good", "bad", "dark", "bright", "hot",
              "cold", "fast", "slow"], "Qualities"),
            (["social", "talk", "speak", "friend", "enemy", "respect", "insult",
              "command", "ask"], "Social & Communication"),
            (["abstract", "soul", "mind", "thought", "idea", "concept", "truth",
              "lie", "dream", "know", "remember"], "Mental & Abstract"),
            (["everyday", "want", "need", "go", "come", "make", "give", "take"],
             "Core Vocabulary"),
        ]

        for keywords, cat_name in rules:
            if any(k in text for k in keywords):
                # match against existing categories (fuzzy)
                for ec in existing_cats:
                    if cat_name.lower() in ec.lower() or ec.lower() in cat_name.lower():
                        return ec
                return cat_name

        return "Uncategorized"

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

    def get_relations(self, root: str) -> list:
        """Get all semantic relations for a root."""
        rows = self.conn.execute(
            "SELECT root_a, root_b, relation, notes FROM semantic_relations WHERE root_a = ? OR root_b = ?",
            (root, root)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_synonyms(self, root: str) -> list:
        """Get synonym roots."""
        rows = self.conn.execute(
            "SELECT root_b FROM semantic_relations WHERE root_a = ? AND relation = 'synonym' UNION SELECT root_a FROM semantic_relations WHERE root_b = ? AND relation = 'synonym'",
            (root, root)
        ).fetchall()
        return [r[0] for r in rows]

    # ─── Export ─────────────────────────────────────────────────

    def export_markdown(self, path: Optional[Path] = None) -> str:
        """Generate a clean markdown lexicon from the DB."""
        out_path = path or LEXICON_MD
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

    # ─── Migration from markdown ────────────────────────────────

    def migrate_from_markdown(self, md_path: Optional[Path] = None):
        """One-time migration: parse the old markdown lexicon into the DB.
        Only imports if the DB is empty."""
        md = md_path or LEXICON_MD
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
        
        # Glottal stop cannot appear word-initially
        if root.startswith("'"):
            issues.append("glottal stop cannot be word-initial")
        
        # q cannot be followed by i in the same syllable
        for i in range(len(root) - 1):
            if root[i] == 'q' and root[i+1] == 'i':
                issues.append("q followed by i (uvular + high front disallowed)")
        
        # No gemination (doubled consonants) — but xx at compound boundaries is tolerated
        # True gemination = same consonant doubled within a single morpheme
        for i in range(len(root) - 1):
            c = root[i]
            if c == root[i+1] and c not in vowels:
                # Check if this is a legitimate compound boundary (xx is common in compounds)
                if c == 'x':
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
