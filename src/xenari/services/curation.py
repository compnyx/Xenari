from typing import Optional

from ..paths import generated_dictionary_path


class CurationMixin:
    def add_root(self, english: str, root: str, meaning: str, category: Optional[str] = None) -> bool:
        """Add a new root to the canonical DB and refresh in-memory lookup data."""
        guessed = category or self.db._guess_category(english, meaning)
        ok, messages = self.db.add_root(english, root, meaning, category=guessed)
        for message in messages:
            print(f"[add] {message}")
        if ok:
            self._load_from_db()
        return ok

    def coin_root(
        self,
        english: str,
        meaning: str = "",
        root: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 8,
        dry_run: bool = True,
        yes: bool = False,
        include_site: bool = False,
    ):
        """Root-coining workflow: inspect neighbors, propose roots, and optionally add one."""
        english = english.lower().strip()
        meaning = meaning.strip() or english
        guessed = category or self.db._guess_category(english, meaning)
        proposals = self.db.propose_root(english, meaning, limit=limit)
        near = self.db.near_meanings(meaning, limit=5)
        if not near and meaning != english:
            near = self.db.near_meanings(english, limit=5)

        lines = [f"Coin root: {english!r} — {meaning}", f"Category guess: {guessed}"]
        existing = self.lookup(english)
        if existing[0]:
            lines.append(f"Existing English mapping: {english} -> {existing[0]} — {existing[1]}")

        lines.append("")
        lines.append("Near existing meanings:")
        if near:
            for item in near:
                lines.append(
                    f"  - {item['root']} — {item['meaning']} "
                    f"[{item['category']}] score={item.get('score', 0)}"
                )
        else:
            lines.append("  none")

        lines.append("")
        lines.append("Candidate roots:")
        if proposals:
            for item in proposals:
                lines.append(
                    f"  - {item['root']} [{item['category']}] "
                    f"score={item.get('score', 0)}: {'; '.join(item['notes'])}"
                )
        else:
            lines.append("  none")

        chosen = root.strip() if root else None
        if not chosen:
            if proposals:
                best = proposals[0]["root"]
                lines.extend([
                    "",
                    "No write requested.",
                    f"Preview with: python3 xenari_tool.py coin {english!r} {meaning!r} --root {best} --dry-run",
                    f"Write with:   python3 xenari_tool.py coin {english!r} {meaning!r} --root {best} --yes",
                ])
            return True, "\n".join(lines)

        lines.extend(["", f"Selected root: {chosen}"])
        issues = self.db.validate_phonotactics(chosen)
        if issues:
            lines.append("INVALID root form:")
            for issue in issues:
                lines.append(f"  - {issue}")
            return False, "\n".join(lines)
        if self.db.has_root(chosen):
            row = self.db.lookup_root(chosen)
            lines.append(f"Root already exists: {chosen} — {row['meaning']} [{row['category']}]")
            return False, "\n".join(lines)

        proposal_roots = {item["root"] for item in proposals}
        if chosen not in proposal_roots:
            lines.append("Warning: selected root was not in the proposal list; treating it as manual but valid.")

        ok, messages = self.db.add_root(
            english,
            chosen,
            meaning,
            category=guessed,
            notes="coined via xenari_tool coin",
            dry_run=dry_run or not yes,
        )
        lines.extend(messages)
        if dry_run or not yes:
            if ok:
                lines.append("No write performed. Re-run with --yes after reading the preview.")
            return ok, "\n".join(lines)

        if ok:
            self._load_from_db()
            lines.append("Wrote root.")
            lines.append(self.sync_exports(include_site=include_site))
            doctor_ok, doctor_report = self.doctor()
            lines.append(doctor_report)
            ok = ok and doctor_ok
        return ok, "\n".join(lines)

    def sync_exports(self, include_site: bool = False) -> str:
        """Regenerate derived JSON exports from the canonical DB."""
        json_text = self.db.export_json()
        out_paths = [generated_dictionary_path()]
        if include_site:
            site = self.site_root
            out_paths.extend([
                site / "src" / "data" / "xenari-dict.json",
                site / "public" / "xenari-dict-data.json",
            ])

        lines = []
        for path in out_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_text, encoding="utf-8")
            lines.append(f"wrote {path}")
        return "\n".join(lines)
