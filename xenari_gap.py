"""Compatibility imports for Xenari vocabulary-gap tooling."""

from xenari_compat import ensure_src

ensure_src()

from xenari.services.gap import GapEntry, GapHarvester, GapOccurrence, Token

__all__ = ["GapEntry", "GapHarvester", "GapOccurrence", "Token"]
