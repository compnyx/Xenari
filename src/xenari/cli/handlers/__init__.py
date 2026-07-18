"""Cohesive command handler groups for the Xenari CLI."""

from .curation import COMMANDS as CURATION_COMMANDS, handle as handle_curation
from .maintenance import COMMANDS as MAINTENANCE_COMMANDS, handle as handle_maintenance
from .query import COMMANDS as QUERY_COMMANDS, handle as handle_query
from .translation import COMMANDS as TRANSLATION_COMMANDS, handle as handle_translation

__all__ = [
    "CURATION_COMMANDS",
    "MAINTENANCE_COMMANDS",
    "QUERY_COMMANDS",
    "TRANSLATION_COMMANDS",
    "handle_curation",
    "handle_maintenance",
    "handle_query",
    "handle_translation",
]
