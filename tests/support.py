"""Shared imports and repository fixtures for Xenari tests."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from xenari_db import XenariDB
from xenari_gap import GapHarvester
from xenari_tool import Xenari


def load_fixtures():
    return json.loads(
        (REPO / "data" / "translator-fixtures.json").read_text(encoding="utf-8")
    )


__all__ = [
    "GapHarvester",
    "Path",
    "REPO",
    "Xenari",
    "XenariDB",
    "json",
    "load_fixtures",
    "shutil",
    "subprocess",
    "sys",
]
