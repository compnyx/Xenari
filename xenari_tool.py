#!/usr/bin/env python3
"""Compatibility entrypoint for the Xenari tool.

Import `Xenari` from here as before; implementation lives in `src/xenari`.
"""

from xenari_compat import ensure_src

ensure_src()

from xenari import Xenari
from xenari.cli import main

__all__ = ["Xenari", "main"]


if __name__ == "__main__":
    main()
