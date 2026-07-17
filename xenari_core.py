"""Compatibility import for the packaged Xenari facade."""

from xenari_compat import ensure_src

ensure_src()

from xenari.facade import Xenari

__all__ = ["Xenari"]
