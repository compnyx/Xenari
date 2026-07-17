"""Compatibility import for the packaged Xenari database."""

from xenari_compat import ensure_src

ensure_src()

from xenari.db import XenariDB

__all__ = ["XenariDB"]
