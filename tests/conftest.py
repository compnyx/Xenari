"""Shared pytest fixtures for canon-safe Xenari tests."""

import shutil
import subprocess
import sys

import pytest

from xenari import Xenari
from xenari.db import XenariDB

from .support import REPO


@pytest.fixture(scope="session")
def xenari():
    """Share one immutable canon instance across read-only behavior tests."""
    instance = Xenari(REPO / "xenari.db", read_only=True)
    yield instance
    instance.close()


@pytest.fixture
def fresh_xenari():
    """Provide an isolated read-only facade for tests that alter in-memory state."""
    instance = Xenari(REPO / "xenari.db", read_only=True)
    yield instance
    instance.close()


@pytest.fixture
def writable_xenari(tmp_path):
    """Provide a writable facade backed by a per-test canon copy."""
    db_path = tmp_path / "xenari.db"
    shutil.copy2(REPO / "xenari.db", db_path)
    instance = Xenari(db_path, read_only=False)
    yield instance
    instance.close()


@pytest.fixture
def writable_db(tmp_path):
    """Provide a writable database wrapper backed by a per-test canon copy."""
    db_path = tmp_path / "xenari.db"
    shutil.copy2(REPO / "xenari.db", db_path)
    database = XenariDB(db_path, read_only=False)
    yield database
    database.close()


@pytest.fixture(scope="session")
def run_cli():
    """Run the checkout CLI with one consistent subprocess contract."""

    def run(*args, check=False):
        return subprocess.run(
            [sys.executable, "xenari_tool.py", *(str(arg) for arg in args)],
            cwd=REPO,
            check=check,
            capture_output=True,
            text=True,
        )

    return run
