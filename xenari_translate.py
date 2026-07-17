"""Compatibility import for the packaged translation engine."""

from xenari_compat import ensure_src

ensure_src()

from xenari.translate import TranslatorMixin

__all__ = ["TranslatorMixin"]
