"""Exception hierarchy for BYOA."""

from __future__ import annotations


class ByoaError(Exception):
    """Base class for all BYOA errors."""


class AdapterError(ByoaError):
    """Raised when an object cannot be adapted into an Agent, or an adapter fails."""


class BlueprintError(ByoaError):
    """Raised when a line's topology is invalid (dangling deps, duplicate nodes)."""


class CycleError(BlueprintError):
    """Raised when the assembly line contains a cycle (not a DAG)."""


class GateFailed(ByoaError):
    """Raised (internally) when a station's quality gate blocks advancement."""


class StationTimeout(ByoaError):
    """Raised when a station exceeds its timeout or the run deadline."""


class MissingDependencyError(ByoaError):
    """Raised when an optional extra is required but not installed."""

    def __init__(self, feature: str, extra: str) -> None:
        super().__init__(
            f"{feature} requires the optional '{extra}' extra. "
            f"Install it with: pip install 'byoa-sdk[{extra}]'"
        )
        self.feature = feature
        self.extra = extra
