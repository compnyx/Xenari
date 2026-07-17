"""Repository and integration paths used by Xenari tooling."""

import os
from pathlib import Path
from typing import Optional, Union


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent
CANON_DB = PACKAGE_ROOT / "data" / "xenari.db"
DATA_DIR = REPO_ROOT / "data"
TRANSLATOR_FIXTURES = DATA_DIR / "translator-fixtures.json"
GENERATED_DICTIONARY = DATA_DIR / "xenari-dict.json"


def resolve_site_root(value: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the nyx-site integration without a host-specific path."""
    configured = value or os.environ.get("XENARI_SITE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "nyx-site").resolve()
