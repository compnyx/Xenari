"""Compatibility import for Xenari health checks."""

from xenari_compat import ensure_src

ensure_src()

from xenari.services.health import HealthMixin

__all__ = ["HealthMixin"]
