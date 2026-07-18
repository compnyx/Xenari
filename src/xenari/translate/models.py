"""Typed internal boundaries shared by translation pipeline stages."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class TranslationMatch:
    """A terminal result produced by one ordered translation stage."""

    stage: str
    text: str


@dataclass(frozen=True, slots=True)
class ForwardClauseRequest:
    """Normalized inputs and resolved context for one forward clause."""

    source: str
    normalized: str
    tense: str
    evidential: str
    evidence_root: str
    terminal_question: bool
    terminal_yes_no_question: bool


@dataclass(slots=True)
class ForwardClauseState:
    """Classified generic clause fields before OSV rendering."""

    tense: str
    evidential: str
    question: bool
    subject: Optional[str] = None
    subject_plural: bool = False
    object: Optional[str] = None
    object_possessive: bool = False
    verb: Optional[str] = None
    copula: bool = False
    negated: bool = False
    interrogative_root: Optional[str] = None
    object_roots: list[str] = field(default_factory=list)
    unknown_words: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CommonPatternRequest:
    """Inputs shared by ordered common-frame recognizers."""

    normalized: str
    evidence_root: str
    terminal_question: bool = False


@dataclass(frozen=True, slots=True)
class ReverseRequest:
    """Normalized input for reverse translation stages."""

    source: str
    clean: str


@dataclass(frozen=True, slots=True)
class ReverseSegments:
    """Clause-frame segmentation result for a reverse translation."""

    frames: tuple[str, ...]
    purpose_frame_indexes: frozenset[int]
    recovered_boundary: bool


@dataclass(slots=True)
class ReverseClause:
    """Parsed roles and diagnostics for one reverse clause frame."""

    object: str = ""
    subject: str = ""
    location: str = ""
    goal: str = ""
    instrument: str = ""
    verb: str = ""
    interrogative: str = ""
    tense: str = "sa"
    negated: bool = False
    question: bool = False
    polite: bool = False
    connector: str = ""
    temporal_modifiers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    loose_fragments: list[str] = field(default_factory=list)
