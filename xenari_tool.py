#!/usr/bin/env python3
"""Compatibility entrypoint for the Xenari tool.

Import `Xenari` from here as before; CLI implementation lives in `xenari_cli`.
"""

from xenari_core import Xenari
from xenari_cli import main

__all__ = ["Xenari", "main"]


if __name__ == "__main__":
    main()
