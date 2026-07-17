"""Bootstrap the src-layout package for repository compatibility entrypoints."""

import sys
from pathlib import Path


def ensure_src() -> None:
    src = str(Path(__file__).resolve().parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
