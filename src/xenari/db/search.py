import hashlib
import re
from typing import Dict, List, Optional, Tuple


class SearchMixin:
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
        inflected_past = key + ("d" if key.endswith("e") else "ed")
        if head == inflected_past:
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

    def stats(self) -> str:
        roots = self.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0]
        maps = self.conn.execute("SELECT COUNT(*) FROM english_map").fetchone()[0]
        cats = self.conn.execute("SELECT COUNT(DISTINCT category) FROM roots").fetchone()[0]
        return f"Roots: {roots} | English mappings: {maps} | Categories: {cats}"

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

    def near_meanings(self, query: str, limit: int = 12) -> List[Dict]:
        """Return ranked near matches for a proposed English meaning."""
        return self.search(query, limit=limit)

    def get_synonyms(self, root: str) -> list:
        """Get synonym roots."""
        rows = self.conn.execute(
            "SELECT root_b FROM semantic_relations WHERE root_a = ? AND relation = 'synonym' UNION SELECT root_a FROM semantic_relations WHERE root_b = ? AND relation = 'synonym'",
            (root, root)
        ).fetchall()
        return [r[0] for r in rows]
