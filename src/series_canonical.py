"""
Backward-compatible wrappers for v0.4 canonical series registry.
"""

from src.series_registry import canonical_series_values, resolve_series as _resolve

CANONICAL_SERIES = canonical_series_values()


def resolve_series(domain: str, series_raw: str | None) -> str:
    return _resolve(series_raw, domain)
