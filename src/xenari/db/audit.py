import datetime
import json
import re
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class AuditMixin:
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
