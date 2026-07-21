"""Structured honesty metadata for deterministic translation output."""

from __future__ import annotations

import re
from typing import Literal, TypedDict

TranslationStatus = Literal["complete", "partial", "unsupported"]


class TranslationReport(TypedDict):
    schema: str
    source: str
    direction: str
    output: str
    status: TranslationStatus
    confidence: Literal["high", "medium", "low"]
    diagnostics: list[str]


_DIAGNOSTIC_RE = re.compile(
    r"\[(?:untranslated|partial|warning|fragment|unknown):[^\]]+\]"
)


def build_translation_report(*, source: str, direction: str, output: str) -> TranslationReport:
    """Classify explicit translator markers without pretending to judge semantics."""
    diagnostics = _DIAGNOSTIC_RE.findall(output)
    if "[untranslated:" in output or "[unknown:" in output:
        status: TranslationStatus = "unsupported"
        confidence: Literal["high", "medium", "low"] = "low"
    elif diagnostics:
        status = "partial"
        confidence = "medium"
    else:
        status = "complete"
        confidence = "high"
    return {
        "schema": "xenari.translation_report.v1",
        "source": source,
        "direction": direction,
        "output": output,
        "status": status,
        "confidence": confidence,
        "diagnostics": diagnostics,
    }
