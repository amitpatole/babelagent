"""Exception hierarchy for Babelagent."""

from __future__ import annotations


class BabelagentError(Exception):
    """Base class for all Babelagent errors."""


class AdapterError(BabelagentError):
    """Raised when an object cannot be adapted into an Agent, or an adapter fails."""


class TopologyError(BabelagentError):
    """Raised when a graph is invalid (dangling deps, duplicate nodes)."""


class CycleError(TopologyError):
    """Raised when the graph contains a cycle (not a DAG)."""


class GateFailed(BabelagentError):
    """Raised (internally) when a node's quality gate blocks the exchange."""


class NodeTimeout(BabelagentError):
    """Raised when a node exceeds its timeout or the run deadline."""


class MissingDependencyError(BabelagentError):
    """Raised when an optional extra is required but not installed."""

    def __init__(self, feature: str, extra: str) -> None:
        super().__init__(
            f"{feature} requires the optional '{extra}' extra. "
            f"Install it with: pip install 'babelagent[{extra}]'"
        )
        self.feature = feature
        self.extra = extra
