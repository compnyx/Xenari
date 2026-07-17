"""Compatibility import for Xenari mutation helpers."""

from xenari_compat import ensure_src

ensure_src()

from xenari.services.mutation import MutationMixin

__all__ = ["MutationMixin"]
