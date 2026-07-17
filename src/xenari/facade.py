#!/usr/bin/env python3
"""Core Xenari facade assembled from focused tool mixins."""

from pathlib import Path
from typing import Dict, Optional

from .db import XenariDB
from .grammar import load_grammar_state
from .paths import resolve_site_root
from .services.export import ExportMixin
from .services.health import HealthMixin
from .services.llm import LlmMixin
from .services.lookup import LookupMixin
from .services.mutation import MutationMixin
from .translate import TranslatorMixin


class Xenari(LookupMixin, TranslatorMixin, LlmMixin, ExportMixin, HealthMixin, MutationMixin):
    def __init__(
        self,
        db_path: Optional[Path] = None,
        *,
        read_only: bool = False,
        site_root: Optional[Path] = None,
    ):
        self.db = XenariDB(db_path, read_only=read_only)
        self.site_root = resolve_site_root(site_root)
        self.lexicon: Dict[str, str] = {}          # root -> meaning
        self.english_to_root: Dict[str, str] = {}  # english -> root
        self._load_from_db()

        load_grammar_state(self)

    def _load_from_db(self):
        """Load all roots and english mappings from the sqlite DB."""
        self.lexicon.clear()
        self.english_to_root.clear()
        for row in self.db.conn.execute("SELECT root, meaning FROM roots"):
            self.lexicon[row["root"]] = row["meaning"].lower()
        for row in self.db.conn.execute("SELECT english_key, root, context_note FROM english_map JOIN roots ON roots.id = english_map.root_id"):
            key = row["english_key"].lower()
            if key not in self.english_to_root:
                self.english_to_root[key] = row["root"]
            else:
                current = self.english_to_root[key]
                current_score = self.db._lookup_score(key, self.lexicon.get(current, ""))
                candidate_score = self.db._lookup_score(key, self.lexicon.get(row["root"], ""), row["context_note"])
                if candidate_score > current_score:
                    self.english_to_root[key] = row["root"]
        preferred = {
            "language": "zuqra",
        }
        for key, root in preferred.items():
            if root in self.lexicon:
                self.english_to_root[key] = root
        self._meaning_synonym_index = {}
        for root, meaning in self.lexicon.items():
            keys = self._meaning_keys(meaning)
            for key in keys:
                score = 3 if keys and keys[0] == key else 2
                current = self._meaning_synonym_index.get(key)
                if current is None or score > current[1]:
                    self._meaning_synonym_index[key] = (root, score)
