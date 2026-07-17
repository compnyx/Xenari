"""Compatibility import for the packaged Xenari CLI."""

from xenari_compat import ensure_src

ensure_src()

from xenari.cli import main

__all__ = ["main"]
