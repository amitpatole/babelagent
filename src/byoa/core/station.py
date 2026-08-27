"""A station: one node on the line wrapping an agent plus an optional gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent import Agent
from .verdict import GateMode


@dataclass
class Station:
    """A workstation on the assembly line.

    Wraps a single :class:`Agent`, plus an optional quality ``check`` whose
    verdict can gate advancement (per ``gate`` mode), and an optional
    per-station ``timeout_s``.
    """

    name: str
    agent: Agent
    check: Any | None = None  # verdict.Check (sync or async); Any to keep runtime light
    gate: GateMode = GateMode.WARN
    timeout_s: float | None = None
