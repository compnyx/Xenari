"""Repository and integration paths used by Xenari tooling."""

import os
from importlib.resources import files
from pathlib import Path
from typing import Optional, Union


PACKAGE_ROOT = Path(__file__).resolve().parent
CANON_DB = PACKAGE_ROOT / "data" / "xenari.db"
TRANSLATOR_FIXTURES = files("xenari").joinpath("data", "translator-fixtures.json")


def resolve_repo_root() -> Optional[Path]:
    """Return the source checkout when one exists.

    Runtime resources live inside the package. Repository-only artifacts must
    not be inferred from arbitrary ``site-packages`` parent directories.
    """
    configured = os.environ.get("XENARI_REPO_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    candidate = PACKAGE_ROOT.parents[1]
    if (candidate / "pyproject.toml").is_file() and (candidate / "data").is_dir():
        return candidate
    return None


def generated_dictionary_path() -> Path:
    """Resolve the generated repo dictionary or an explicit override."""
    configured = os.environ.get("XENARI_GENERATED_DICTIONARY")
    if configured:
        return Path(configured).expanduser().resolve()
    repo_root = resolve_repo_root()
    if repo_root is None:
        raise RuntimeError(
            "generated dictionary path is source-checkout-only; set "
            "XENARI_GENERATED_DICTIONARY to an explicit output path"
        )
    return repo_root / "data" / "xenari-dict.json"


def resolve_site_root(value: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the nyx-site integration without a host-specific path."""
    configured = value or os.environ.get("XENARI_SITE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "nyx-site").resolve()
