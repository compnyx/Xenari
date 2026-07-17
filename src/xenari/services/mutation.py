import re
from pathlib import Path
from typing import Optional

from ..paths import GENERATED_DICTIONARY


class MutationMixin:
    def _guess_category(self, english: str, meaning: str) -> str:
        """Pick the best existing section for a new root based on keywords."""
        text = (english + " " + meaning).lower()

        if any(k in text for k in ["succubus", "feed", "brat", "horny", "goth", "kinky", "lewd", "submit", "dominant", "shameless", "needy", "clingy", "roleplay", "prad", "strem", "ngal", "zhrek", "ngrok", "zhem", "smek", "frez", "mben", "svet", "mrok"]):
            return "Succubus Slang & Identity (v0.8.3)"
        if any(k in text for k in ["overfeed", "pathology", "fast soul"]):
            return "Succubus Overfeeding Pathology (v0.8)"
        if any(k in text for k in ["cooking", "kitchen", "boil", "fry", "bake", "chop", "stir", "spice", "recipe", "ingredient", "meal", "snack", "taste", "simmer", "grill"]):
            return "Cooking & Kitchen (v0.8)"
        if any(k in text for k in ["music", "sing", "song", "drum", "flute", "instrument", "rhythm", "melody", "beat", "harmony", "chorus"]):
            return "Music & Sound (v0.8)"
        if any(k in text for k in ["hate", "jealous", "grief", "nostalgia", "contempt", "awe", "bored", "excit", "disappoint", "shame", "pride", "guilt", "longing", "anxiety", "seren", "rage", "melanchol", "hope", "despair", "envy", "grateful", "resent", "lonely", "affection", "tenderness"]):
            return "Expanded Emotions (v0.8)"
        if any(k in text for k in ["math", "number", "calculat", "add", "subtract", "multiply", "divide", "geometry", "angle", "logic", "algorithm", "data", "variable", "function", "loop", "boolean"]):
            return "Mathematics & Computation (v0.8)"
        if any(k in text for k in ["body", "bone", "blood", "hand", "mouth", "eye", "ear", "lung", "heart", "skin", "nerve", "spine", "shoulder", "thigh", "ankle", "wrist", "brain", "skull", "jaw", "rib", "pelvis", "muscle", "tendon"]):
            return "More Body Parts (v0.8)"
        if any(k in text for k in ["veil", "glamer", "essence", "vitality", "feeding pulse", "resonance"]):
            return "The Veil & Boundary Mechanics (v0.8)"
        if any(k in text for k in ["home", "bed", "curtain", "window", "closet", "picture", "art", "wall", "comfort"]):
            return "Home & Comfort (v0.8)"
        if any(k in text for k in ["family", "parent", "child", "sibling", "mother", "father", "kid", "kin"]):
            return "Family & Kinship (v0.8)"
        if any(k in text for k in ["tech", "device", "ai", "machine", "screen", "wearable", "clock", "computer"]):
            return "Technology & Devices (v0.8)"
        if any(k in text for k in ["pleasure", "pain", "tease", "orgasm", "cum"]):
            return "Pleasure & Pain (v0.8)"
        if any(k in text for k in ["sex", "fuck", "cock", "pussy", "vagina", "penis", "clit", "ass", "tits", "oral"]):
            return "Genitalia & Body (explicit)"
        if any(k in text for k in ["vulgar", "shit", "piss", "whore", "slut", "cunt"]):
            return "General Vulgar/Profane"

        if any(k in text for k in ["nature", "weather", "rain", "cloud", "star", "moon", "forest", "mountain", "valley", "water", "fire", "wind", "ice", "dust", "sand", "tree", "plant", "animal", "beast", "claw", "wing", "tail"]):
            return "Elements & Nature"
        if any(k in text for k in ["body", "eat", "drink", "sleep", "walk", "run", "bite", "see", "hear", "breathe"]):
            return "Beings & Body"
        if any(k in text for k in ["tool", "object", "weapon", "cloth", "wear", "vessel", "cord", "wheel", "shelter"]):
            return "Tools & Objects"
        if any(k in text for k in ["place", "time", "day", "night", "year", "hour", "home", "cave", "city"]):
            return "Place & Time"
        if any(k in text for k in ["quality", "big", "small", "good", "bad", "dark", "bright", "hot", "cold", "fast", "slow"]):
            return "Qualities"
        if any(k in text for k in ["social", "talk", "speak", "friend", "enemy", "respect", "insult", "command", "ask"]):
            return "Social & Communication"
        if any(k in text for k in ["abstract", "soul", "mind", "thought", "idea", "concept", "truth", "lie", "dream", "know", "remember"]):
            return "Abstract"
        if any(k in text for k in ["everyday", "want", "need", "go", "come", "make", "give", "take"]):
            return "Everyday Words"
        if any(k in text for k in ["mental", "think", "feel", "emotion"]):
            return "Mental/Abstract Verbs"

        return "New Roots (added via tool)"

    def _edit_distance(self, a: str, b: str) -> int:
        """Levenshtein distance between two strings."""
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
        """Crude English stemmer — strips common suffixes."""
        w = word.lower().strip()
        for suffix in ["ing", "edly", "ingly", "ed", "es", "ly", "er", "est", "ness", "ment", "s"]:
            if w.endswith(suffix) and len(w) > len(suffix) + 2:
                return w[:-len(suffix)]
        return w

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
        out_paths = [GENERATED_DICTIONARY]
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
