#!/usr/bin/env python3
"""
Xenari Database — sqlite source of truth for the Xenari conlang.

Schema:
  roots(id, root, meaning, category, source, timestamp, notes)
  english_map(id, english_key, root_id, context_note, part_of_speech)

Usage:
  from pathlib import Path
  from xenari.db import XenariDB
  with XenariDB(Path("xenari.db")) as db:
      db.lookup("hate")
      db.add_root("hate", "blun", "to hate, detest", category="Mental & Abstract")
      db.search("feed")
      db.export_markdown(Path("xenari-lexicon-export.md"))
"""

import datetime
import re
import sqlite3
from pathlib import Path
from typing import Optional

from ..paths import CANON_DB, resolve_repo_root
from .audit import AuditMixin
from .mutation import MutationMixin
from .pos import POS_SCHEMA_VERSION, PartOfSpeechMixin
from .search import SearchMixin

DB_PATH = CANON_DB


class XenariDB(SearchMixin, MutationMixin, AuditMixin, PartOfSpeechMixin):
    def __init__(self, db_path: Optional[Path] = None, *, read_only: Optional[bool] = None):
        """Open the canonical database.

        The bundled canon opens read-only by default. An explicit ``db_path``
        remains an explicit writable workflow. Writing an installed package's
        bundled resource is rejected; callers should copy the canon and pass
        that destination explicitly instead.

        Read-only opens intentionally use SQLite's ``mode=ro`` and
        ``immutable=1`` URI flags.  Besides making the contract explicit, this
        prevents read commands from creating WAL/SHM sidecars or
        opportunistically initializing a schema.
        """
        if read_only is None:
            read_only = db_path is None
        if not read_only and db_path is None and resolve_repo_root() is None:
            raise RuntimeError(
                "refusing to write the installed package canon; pass an "
                "explicit writable db_path"
            )

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
        existing_version = self._existing_schema_version()
        if existing_version is not None and existing_version != "legacy":
            existing_key = self._schema_version_key(existing_version)
            if existing_key is None:
                raise RuntimeError(f"unrecognized database schema version: {existing_version}")
            current_key = self._schema_version_key(POS_SCHEMA_VERSION)
            if current_key is None:
                raise RuntimeError(f"invalid packaged schema version: {POS_SCHEMA_VERSION}")
            if existing_key > current_key:
                raise RuntimeError(
                    "database schema is newer than this Xenari build: "
                    f"{existing_version} > {POS_SCHEMA_VERSION}"
                )
        has_english_map = self.conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type = 'table' AND name = 'english_map'"""
        ).fetchone()
        if has_english_map is not None and not self._has_part_of_speech_column():
            # Schema changes are real mutations too. Preserve a consistent
            # legacy copy before ALTER TABLE so migrations remain recoverable.
            self._backup_before_mutation("schema-pos-v2")
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
                part_of_speech TEXT CHECK (
                    part_of_speech IS NULL OR part_of_speech IN (
                        'adjective', 'adverb', 'ideophone', 'interjection',
                        'noun', 'numeral', 'particle', 'pronoun',
                        'proper_noun', 'verb'
                    )
                ),
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
        self._ensure_part_of_speech_schema()
        if existing_version != POS_SCHEMA_VERSION:
            self.conn.execute(
                """INSERT INTO tool_meta (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                     value = excluded.value,
                     updated_at = excluded.updated_at""",
                (
                    "schema_version",
                    POS_SCHEMA_VERSION,
                    datetime.datetime.now().isoformat(timespec="seconds"),
                ),
            )
        self.conn.commit()

    def _existing_schema_version(self) -> Optional[str]:
        table = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tool_meta'"
        ).fetchone()
        if table is None:
            return None
        row = self.conn.execute(
            "SELECT value FROM tool_meta WHERE key = 'schema_version'"
        ).fetchone()
        return row[0] if row else None

    @staticmethod
    def _schema_version_key(value: str) -> Optional[tuple[int, int, int, int]]:
        match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})\.(\d+)", value or "")
        if match is None:
            return None
        return tuple(int(part) for part in match.groups())

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
