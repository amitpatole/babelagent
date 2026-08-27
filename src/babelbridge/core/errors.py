"""Exception hierarchy for Babelbridge."""

from __future__ import annotations


class BabelbridgeError(Exception):
    """Base class for all Babelbridge errors."""


class AdapterError(BabelbridgeError):
    """Raised when an object cannot be adapted into an Agent, or an adapter fails."""


class TopologyError(BabelbridgeError):
    """Raised when a graph is invalid (dangling deps, duplicate nodes)."""


class CycleError(TopologyError):
    """Raised when the graph contains a cycle (not a DAG)."""


class GateFailed(BabelbridgeError):
    """Raised (internally) when a node's quality gate blocks the exchange."""


class NodeTimeout(BabelbridgeError):
    """Raised when a node exceeds its timeout or the run deadline."""


class MissingDependencyError(BabelbridgeError):
    """Raised when an optional extra is required but not installed."""

    def __init__(self, feature: str, extra: str) -> None:
        super().__init__(
            f"{feature} requires the optional '{extra}' extra. "
            f"Install it with: pip install 'babelbridge[{extra}]'"
        )
        self.feature = feature
        self.extra = extra
