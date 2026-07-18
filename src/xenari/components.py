"""Explicit service components used by the :class:`xenari.Xenari` facade.

The implementation mixins predate the packaged API.  Keeping them behind
small bound services lets each responsibility have an explicit home without
copying their behavior or making callers depend on the mixin hierarchy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .services.curation import CurationMixin
from .services.export import ExportMixin
from .services.health import HealthMixin
from .services.llm import LlmMixin
from .services.lookup import LookupMixin
from .translate import TranslatorMixin

if TYPE_CHECKING:
    from .facade import Xenari


class BoundService:
    """A stateless service that reads shared state through its owning facade."""

    __slots__ = ("_owner",)

    def __init__(self, owner: Xenari) -> None:
        self._owner = owner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._owner, name)


class LexiconService(LookupMixin, BoundService):
    """Lexicon lookup, synonym lookup, animacy, and compounding behavior."""

    __slots__ = ()


class TranslationService(TranslatorMixin, LlmMixin, BoundService):
    """Forward/reverse translation plus the model-facing translation bridge."""

    __slots__ = ()


class CurationService(ExportMixin, CurationMixin, BoundService):
    """Canon curation and generated-artifact export behavior."""

    __slots__ = ()


class HealthService(HealthMixin, BoundService):
    """Read-only validation, parity, audit, and review workflows."""

    __slots__ = ()


SERVICE_TYPES = {
    "lexicon_service": LexiconService,
    "translator": TranslationService,
    "curation": CurationService,
    "health": HealthService,
}


def compatibility_routes() -> dict[str, str]:
    """Map legacy facade attributes to their explicit owning service.

    Attributes implemented by the behavior mixins are routed, including the
    immutable shared tables that were historically visible on ``Xenari``.
    Component plumbing such as ``__getattr__`` deliberately stays private.
    """

    routes: dict[str, str] = {}
    for service_name, service_type in SERVICE_TYPES.items():
        for base in service_type.__mro__:
            if base in {service_type, BoundService, object}:
                continue
            for name, _value in vars(base).items():
                if name.startswith("__"):
                    continue
                routes.setdefault(name, service_name)
    return routes


COMPATIBILITY_ROUTES = compatibility_routes()


__all__ = [
    "CurationService",
    "HealthService",
    "LexiconService",
    "TranslationService",
]
