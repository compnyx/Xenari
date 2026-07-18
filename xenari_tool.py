#!/usr/bin/env python3
"""Repository entrypoint for the packaged Xenari tool."""

import sys
from pathlib import Path

src = str(Path(__file__).resolve().parent / "src")
if src not in sys.path:
    sys.path.insert(0, src)

from xenari import Xenari  # noqa: E402
from xenari.cli import main  # noqa: E402

__all__ = ["Xenari", "main"]


if __name__ == "__main__":
    main()
