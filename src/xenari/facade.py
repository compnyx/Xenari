#!/usr/bin/env python3
"""Thin compatibility facade over explicit Xenari service components."""

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .components import (
    COMPATIBILITY_ROUTES,
    CurationService,
    HealthService,
    LexiconService,
    TranslationService,
)
from .db import XenariDB
from .grammar import DEFAULT_GRAMMAR, GrammarConfig, PronounSpec
from .paths import resolve_site_root


class Xenari:
    """Public API and shared state for the Xenari toolchain.

    New code may use the explicit ``lexicon_service``, ``translator``,
    ``curation``, and ``health`` components.  Established calls such as
    ``xenari.speak(...)`` remain supported through compatibility forwarding.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        *,
        read_only: Optional[bool] = None,
        site_root: Optional[Path] = None,
        grammar: GrammarConfig = DEFAULT_GRAMMAR,
    ):
        self.db = XenariDB(db_path, read_only=read_only)
        self.site_root = resolve_site_root(site_root)
        self.grammar = grammar
        self.lexicon: Dict[str, str] = {}          # root -> meaning
        self.english_to_root: Dict[str, str] = {}  # english -> root
        self.english_part_of_speech: Dict[str, str] = {}
        # ``lexicon`` is an established public dictionary, so the explicit
        # lexicon component uses the unambiguous ``lookup_service`` name.
        self.lexicon_service = LexiconService(self)
        self.translator = TranslationService(self)
        self.curation = CurationService(self)
        self.health = HealthService(self)
        self._load_from_db()

    def __getattr__(self, name: str) -> Any:
        """Forward an established flat API attribute to its owning service."""

        service_name = COMPATIBILITY_ROUTES.get(name)
        if service_name is None:
            raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")
        service = object.__getattribute__(self, service_name)
        return getattr(service, name)

    def __dir__(self) -> list[str]:
        """Include compatibility-forwarded methods in interactive discovery."""

        return sorted(set(super().__dir__()) | set(COMPATIBILITY_ROUTES))

    # Compatibility aliases keep the established translator/mixin API thin
    # while grammar state now has one explicit, immutable owner.
    @property
    def p(self) -> Mapping[str, str]:
        return self.grammar.particles

    @property
    def pronouns(self) -> Mapping[str, str]:
        return self.grammar.pronouns

    @property
    def en_pronouns(self) -> Mapping[str, PronounSpec]:
        return self.grammar.english_pronouns

    @property
    def tense_map(self) -> Mapping[str, str]:
        return self.grammar.tense_roots

    @property
    def evidential_map(self) -> Mapping[str, str]:
        return self.grammar.evidential_roots

    @property
    def verb_map(self) -> Mapping[str, str]:
        return self.grammar.verb_roots

    @property
    def copula_words(self) -> frozenset[str]:
        return self.grammar.copula_words

    @property
    def skip_words(self) -> frozenset[str]:
        return self.grammar.skip_words

    def close(self):
        """Close the underlying canon database connection."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def _load_from_db(self):
        """Load all roots and english mappings from the sqlite DB."""
        self.lexicon.clear()
        self.english_to_root.clear()
        self.english_part_of_speech.clear()
        for row in self.db.conn.execute("SELECT root, meaning FROM roots"):
            self.lexicon[row["root"]] = row["meaning"].lower()
        pos_column = (
            "english_map.part_of_speech"
            if self.db._has_part_of_speech_column()
            else "NULL AS part_of_speech"
        )
        for row in self.db.conn.execute(
            f"""SELECT english_key, root, context_note, {pos_column}
                FROM english_map JOIN roots ON roots.id = english_map.root_id"""
        ):
            key = row["english_key"].lower()
            if key not in self.english_to_root:
                self.english_to_root[key] = row["root"]
                if row["part_of_speech"]:
                    self.english_part_of_speech[key] = row["part_of_speech"]
            else:
                current = self.english_to_root[key]
                current_score = self.db._lookup_score(key, self.lexicon.get(current, ""))
                candidate_score = self.db._lookup_score(key, self.lexicon.get(row["root"], ""), row["context_note"])
                if candidate_score > current_score:
                    self.english_to_root[key] = row["root"]
                    if row["part_of_speech"]:
                        self.english_part_of_speech[key] = row["part_of_speech"]
                    else:
                        self.english_part_of_speech.pop(key, None)
        preferred = {
            "language": "zuqra",
        }
        for key, root in preferred.items():
            if root in self.lexicon:
                self.english_to_root[key] = root
                self.english_part_of_speech.pop(key, None)
        self._meaning_synonym_index = {}
        for root, meaning in self.lexicon.items():
            keys = self._meaning_keys(meaning)
            for key in keys:
                score = 3 if keys and keys[0] == key else 2
                current = self._meaning_synonym_index.get(key)
                if current is None or score > current[1]:
                    self._meaning_synonym_index[key] = (root, score)
