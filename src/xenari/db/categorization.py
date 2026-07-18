import re
from typing import Dict, Tuple


class CategorizationMixin:
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
              "melody", "beat", "harmony", "chorus"],
             "Arts & Culture"),
            (["boom", "sound", "noise", "audio"], "Sound & Voice"),
            (["hate", "jealous", "grief", "nostalgia", "contempt", "awe", "bored",
              "excit*", "disappoint*", "shame", "pride", "guilt", "longing", "anxiety",
              "seren*", "rage", "anger", "angry", "wrath", "melanchol*", "hope", "despair", "envy", "grateful",
              "resent*", "lonely", "affection", "tenderness", "despise", "scorn",
              "disdain", "solitude", "lonely", "alone"], "Mental & Abstract"),
            (["math", "number", "calculat*", "add", "subtract", "multiply", "divide",
              "geometry", "angle", "logic", "algorithm", "data", "variable",
              "function", "loop", "boolean"], "Mathematics & Computation"),
            (["body", "bone", "blood", "hand", "mouth", "eye", "ear", "lung",
              "heart", "skin", "nerve", "spine", "shoulder", "thigh", "ankle",
              "wrist", "brain", "skull", "jaw", "rib", "pelvis", "muscle", "tendon"],
             "Body Parts"),
            (["veil", "glamer", "essence", "vitality", "feeding pulse", "resonance"],
             "Cosmology & Reality"),
            (["heaven", "heavens", "cosmos", "reality", "universe", "god"], "Cosmology & Reality"),
            (["home", "bed", "curtain", "window", "closet", "picture", "art",
              "wall", "comfort"], "Home & Comfort"),
            (["family", "parent", "child", "sibling", "mother", "father", "kid", "kin"],
             "Family & Kinship"),
            (["tech", "device", "ai", "machine", "screen", "wearable", "clock", "computer",
              "motherboard", "airbag", "airbags", "hardware"],
             "Technology & Devices"),
            (["assess", "assesses", "assessment"], "Perception & Cognition"),
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
              "wheel", "shelter", "handrail"], "Tools & Objects"),
            (["place", "time", "day", "night", "nighttime", "nightfall", "year", "hour", "home", "cave", "city"],
             "Place & Time"),
            (["facility", "facilities", "building", "room", "site"], "Place & Time"),
            (["quality", "big", "small", "good", "bad", "dark", "darken", "darkens", "bright", "hot",
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
            matched = []
            for keyword in keywords:
                stem = keyword.endswith("*")
                value = keyword.removesuffix("*")
                suffix = "" if stem else r"(?![a-z])"
                if re.search(rf"(?<![a-z]){re.escape(value)}{suffix}", text):
                    matched.append(value)
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
