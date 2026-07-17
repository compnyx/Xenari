"""Compatibility import for Xenari LLM helpers."""

from xenari_compat import ensure_src

ensure_src()

from xenari.services.llm import LlmMixin

__all__ = ["LlmMixin"]
