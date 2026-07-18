"""Repository fixtures shared by Xenari tests."""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_fixtures():
    return json.loads(
        (REPO / "data" / "translator-fixtures.json").read_text(encoding="utf-8")
    )


__all__ = ["REPO", "load_fixtures"]
