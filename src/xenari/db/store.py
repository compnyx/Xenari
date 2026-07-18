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
  db.export_markdown(Path("xenari-lexicon-export.md"))
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Optional

from ..paths import CANON_DB
from .audit import AuditMixin
from .mutation import MutationMixin
from .search import SearchMixin

DB_PATH = CANON_DB


class XenariDB(SearchMixin, MutationMixin, AuditMixin):
    def __init__(self, db_path: Optional[Path] = None, *, read_only: bool = False):
        """Open the canonical database.

        Read-only opens intentionally use SQLite's ``mode=ro`` and
        ``immutable=1`` URI flags.  Besides making the contract explicit, this
        prevents read commands from creating WAL/SHM sidecars or
        opportunistically initializing a schema.
        """
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

            CREATE TABLE IF NOT EXISTS tool_meta (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
        """)
        self.conn.execute(
            """INSERT OR IGNORE INTO tool_meta (key, value, updated_at)
               VALUES (?, ?, ?)""",
            ("schema_version", "2026-07-09.2", datetime.datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
