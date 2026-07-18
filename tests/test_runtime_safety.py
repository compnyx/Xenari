"""Installed-canon safety and connection lifecycle regressions."""

import sqlite3

import pytest

from xenari import Xenari
from xenari.db import XenariDB, store


def test_bundled_canon_defaults_to_read_only():
    with Xenari() as xenari:
        assert xenari.db.read_only is True
        assert xenari.lookup("love") == ("zrent", "loved")

    with XenariDB() as db:
        assert db.read_only is True
        assert db.lookup("love") == ("zrent", "loved")


def test_installed_package_canon_rejects_implicit_writes(monkeypatch):
    monkeypatch.setattr(store, "resolve_repo_root", lambda: None)

    with pytest.raises(RuntimeError, match="explicit writable db_path"):
        XenariDB(read_only=False)


def test_explicit_database_path_preserves_writable_workflow(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "resolve_repo_root", lambda: None)
    db_path = tmp_path / "explicit.db"

    with XenariDB(db_path) as db:
        assert db.read_only is False
        assert db.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'roots'"
        ).fetchone()

    with Xenari(db_path) as xenari:
        assert xenari.db.read_only is False


def test_database_and_facade_context_managers_close_connections(tmp_path):
    db_path = tmp_path / "lifecycle.db"

    with Xenari(db_path) as xenari:
        facade_connection = xenari.db.conn
        assert xenari.db.read_only is False
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        facade_connection.execute("SELECT 1")

    with XenariDB(db_path, read_only=True) as db:
        database_connection = db.conn
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        database_connection.execute("SELECT 1")
