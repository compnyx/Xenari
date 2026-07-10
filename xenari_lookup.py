import re
from typing import List, Optional, Tuple


class LookupMixin:
    def lookup(self, english: str) -> Tuple[Optional[str], Optional[str]]:
        """Look up an English word, return (root, meaning) or (None, None)."""
        key = english.lower().strip()
        if key in self.en_pronouns:
            root = self.pronouns[self.en_pronouns[key][0]]
            return root, self.lexicon.get(root, "")
        if key in self.english_to_root:
            root = self.english_to_root[key]
            return root, self.lexicon.get(root, "")
        root = self._lookup_by_meaning_synonym(key)
        if root:
            return root, self.lexicon.get(root, "")
        return None, None

    def _meaning_keys(self, meaning: str) -> List[str]:
        """Derive conservative lookup keys from the head of a meaning string."""
        head = (meaning or "").lower().replace("—", ";")
        head = re.split(r";|:", head, maxsplit=1)[0]
        head = re.sub(r"\([^)]*\)", "", head)
        keys = []
        for part in re.split(r"[,/]", head):
            part = re.sub(r"^(to|a|an|the)\s+", "", part.strip())
            if re.fullmatch(r"[a-z][a-z'-]{1,}", part):
                keys.append(part)
        return keys

    def _lookup_by_meaning_synonym(self, key: str) -> Optional[str]:
        best = None
        best_score = -1
        for root, meaning in self.lexicon.items():
            keys = self._meaning_keys(meaning)
            if key not in keys:
                continue
            score = 3 if keys and keys[0] == key else 2
            if score > best_score:
                best = root
                best_score = score
        return best

    def lookup_root(self, root: str) -> str:
        """Look up a Xenari root, return its meaning."""
        return self.lexicon.get(root, "unknown root")

    def _safe_root(self, word: str) -> str:
        """Return real root or [unknown:word]. Never hallucinates."""
        root, _ = self.lookup(word)
        return root if root else f"[unknown:{word}]"

    def _is_known(self, word: str) -> bool:
        """Check if a word exists in the lexicon."""
        return word.lower().strip() in self.english_to_root

    def _animacy_for(self, root: str, default: str = "nu") -> str:
        """Best-effort animacy for generated clauses.

        Xenari requires animacy on NPs and verb agreement, but the DB does not
        store animacy as a structured field yet. Pronouns are animate; common
        being/animal/person meanings are treated as animate; everything else
        defaults to inanimate.
        """
        if root in self.pronouns.values():
            return self.p["anim"]
        meaning = self.lexicon.get(root, "").lower()
        animate_cues = (
            "person", "being", "creature", "animal", "stranger", "speaker",
            "addressee", "parent", "child", "sibling", "partner", "friend",
            "enemy", "student", "teacher", "worker", "thief", "robber",
            "demon", "succubus", "human", "body", "soul", "living"
        )
        return (
            self.p["anim"]
            if any(re.search(rf"\b{re.escape(cue)}s?\b", meaning) for cue in animate_cues)
            else default
        )

    def _is_pronoun_root(self, root: str) -> bool:
        """Xenari pronouns carry inherent animacy and do not print vi/nu."""
        return root in self.pronouns.values()

    def compound(self, *english_words: str) -> str:
        """
        Right-headed compounding with ' separator when needed.
        Returns [unknown:word] if any word is missing.
        """
        roots = []
        for w in english_words:
            root, _ = self.lookup(w)
            if root:
                roots.append(root)
            else:
                return f"[unknown:{w}]"

        if not roots:
            return ""
        if len(roots) == 1:
            return roots[0]

        result = roots[0]
        for r in roots[1:]:
            # Insert glottal stop if boundary would create gemination
            if result and result[-1] in "bcdfghjklmnpqrstvwxyz" and r[0] in "bcdfghjklmnpqrstvwxyz":
                result += "'"
            result += r
        return result

    def _try_compound_pair(self, w1: str, w2: str) -> Optional[str]:
        """Try to compound two words. Merge if BOTH words exist individually."""
        r1, _ = self.lookup(w1)
        r2, _ = self.lookup(w2)
        if r1 and r2:
            # Build the compound (right-headed)
            result = r1
            if result[-1] in "bcdfghjklmnpqrstvwxyz" and r2[0] in "bcdfghjklmnpqrstvwxyz":
                result += "'"
            result += r2
            return result
        return None
