"""Compatibility import for Xenari lookup helpers."""

from xenari_compat import ensure_src

ensure_src()

from xenari.services.lookup import LookupMixin

__all__ = ["LookupMixin"]
