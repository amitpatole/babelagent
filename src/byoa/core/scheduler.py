"""The async DAG executor — drives parts through the assembly line.

Reactive scheduling: a node runs as soon as its barrier over upstreams is
satisfied; independent branches run concurrently under a bounded semaphore.
Failures (agent error, timeout, or a blocking gate) propagate through barriers,
skipping nodes that can no longer be satisfied.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .agent import Context
from .blueprint import BarrierKind, Blueprint
from .part import Part, Product
from .verdict import Result, Verdict

# Bound on concurrent stations, so a wide fan-out cannot spawn unbounded tasks.
DEFAULT_CONCURRENCY = 8


class NodeState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


_TERMINAL = {NodeState.DONE, NodeState.FAILED, NodeState.SKIPPED}


@dataclass
class _Outcome:
    name: str
    state: NodeState
    part: Part | None
    result: Result | None
    error: str | None
    elapsed_ms: int


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class _Run:
    """Holds mutable state for a single blueprint execution."""

    def __init__(self, bp: Blueprint, initial: Part, ctx: Context, concurrency: int) -> None:
        self.bp = bp
        self.initial = initial
        self.ctx = ctx
        self.sem = asyncio.Semaphore(max(1, concurrency))
        self.states: dict[str, NodeState] = {n: NodeState.PENDING for n in bp.nodes}
        self.outputs: dict[str, Part] = {}
        self.results: dict[str, Result] = {}
        self.records: list[dict[str, Any]] = []

    # --- barrier logic ----------------------------------------------------
    def _succeeded(self, ups: list[str]) -> list[str]:
        return [u for u in ups if self.states[u] is NodeState.DONE]

    def _settled(self, ups: list[str]) -> bool:
        return all(self.states[u] in _TERMINAL for u in ups)

    def barrier_ready(self, name: str) -> bool:
        node = self.bp.nodes[name]
        ups = node.after
        if not ups:
            return True
        kind = node.barrier.kind
        if kind is BarrierKind.ALL:
            return len(self._succeeded(ups)) == len(ups)
        if kind is BarrierKind.K_OF_N:
            return len(self._succeeded(ups)) >= (node.barrier.k or 1)
        # OPTIONAL: run once everything upstream has settled.
        return self._settled(ups)

    def barrier_impossible(self, name: str) -> bool:
        node = self.bp.nodes[name]
        ups = node.after
        if not ups:
            return False
        failed = [u for u in ups if self.states[u] in (NodeState.FAILED, NodeState.SKIPPED)]
        pending = [u for u in ups if self.states[u] not in _TERMINAL]
        succeeded = self._succeeded(ups)
        kind = node.barrier.kind
        if kind is BarrierKind.ALL:
            return len(failed) > 0
        if kind is BarrierKind.K_OF_N:
            return len(succeeded) + len(pending) < (node.barrier.k or 1)
        return False  # OPTIONAL can always eventually settle

    # --- input assembly ---------------------------------------------------
    def gather_input(self, name: str) -> Part:
        node = self.bp.nodes[name]
        if not node.after:
            return self.initial
        contributing = [u for u in node.after if self.states[u] is NodeState.DONE and u in self.outputs]
        if len(contributing) == 1:
            return self.outputs[contributing[0]]
        merged_payload = {u: self.outputs[u].payload for u in contributing}
        merged_meta: dict[str, Any] = {}
        for u in contributing:
            merged_meta.update(self.outputs[u].meta)
        return Part(payload=merged_payload, meta=merged_meta)

    # --- single node ------------------------------------------------------
    async def run_node(self, name: str) -> _Outcome:
        node = self.bp.nodes[name]
        station = node.station
        part = self.gather_input(name)
        start = time.monotonic()

        timeout = _effective_timeout(station.timeout_s, self.ctx)
        async with self.sem:
            try:
                if timeout is not None and timeout <= 0:
                    raise TimeoutError
                coro = station.agent.run(part, self.ctx)
                out = await (asyncio.wait_for(coro, timeout) if timeout is not None else coro)
            except TimeoutError:
                return _Outcome(name, NodeState.FAILED, None, None,
                                "station timed out", _ms(start))
            except Exception as exc:  # noqa: BLE001 — record any agent failure as a node failure
                return _Outcome(name, NodeState.FAILED, None, None,
                                f"{type(exc).__name__}: {exc}", _ms(start))

            result: Result | None = None
            if station.check is not None:
                try:
                    result = await _maybe_await(station.check(out, self.ctx))
                except Exception as exc:  # noqa: BLE001
                    result = Result.failed(f"check raised {type(exc).__name__}: {exc}")
                if station.gate.blocks(result.verdict):
                    return _Outcome(name, NodeState.FAILED, out, result,
                                    f"gate blocked: {result.reason}", _ms(start))
            return _Outcome(name, NodeState.DONE, out, result, None, _ms(start))

    # --- driver -----------------------------------------------------------
    async def execute(self) -> Product:
        running: dict[str, asyncio.Task[_Outcome]] = {}
        while True:
            progressed = False

            # Mark nodes whose barrier can never be satisfied as skipped.
            for name in self.bp.nodes:
                if self.states[name] is NodeState.PENDING and self.barrier_impossible(name):
                    self.states[name] = NodeState.SKIPPED
                    self.records.append(
                        {"station": name, "state": "skipped",
                         "reason": "upstream barrier unsatisfiable"}
                    )
                    progressed = True

            # Launch every ready node.
            for name in self.bp.nodes:
                if (
                    self.states[name] is NodeState.PENDING
                    and name not in running
                    and self.barrier_ready(name)
                ):
                    self.states[name] = NodeState.RUNNING
                    running[name] = asyncio.create_task(self.run_node(name))

            if running:
                done, _ = await asyncio.wait(
                    running.values(), return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    outcome = task.result()
                    self._absorb(outcome)
                    running.pop(outcome.name, None)
                continue

            if not progressed:
                break

        return self._finish()

    def _absorb(self, outcome: _Outcome) -> None:
        self.states[outcome.name] = outcome.state
        if outcome.part is not None:
            self.outputs[outcome.name] = outcome.part
        if outcome.result is not None:
            self.results[outcome.name] = outcome.result
        self.records.append(
            {
                "station": outcome.name,
                "state": outcome.state.value,
                "verdict": (outcome.result.verdict.value if outcome.result else None),
                "reason": outcome.error or (outcome.result.reason if outcome.result else ""),
                "elapsed_ms": outcome.elapsed_ms,
            }
        )

    def _finish(self) -> Product:
        terminals = self.bp.terminals()
        done_terminals = [t for t in terminals if self.states[t] is NodeState.DONE]
        if len(done_terminals) == 1:
            output: Any = self.outputs[done_terminals[0]].payload
        elif done_terminals:
            output = {t: self.outputs[t].payload for t in done_terminals}
        else:
            output = None

        # The line succeeded if every terminal produced its output. A failure on
        # a branch that a downstream barrier (k_of_n / optional) tolerated is
        # recorded in the trace but does not, by itself, fail the product.
        ok = bool(terminals) and all(self.states[t] is NodeState.DONE for t in terminals)
        verdict = Verdict.worst([r.verdict for r in self.results.values()])
        if not ok:
            verdict = Verdict.FAIL
        return Product(output=output, ok=ok, verdict=verdict.value, trace=self.records)


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _effective_timeout(station_timeout: float | None, ctx: Context) -> float | None:
    rem = ctx.remaining()
    candidates = [t for t in (station_timeout, rem) if t is not None]
    return min(candidates) if candidates else None


async def run_blueprint(
    bp: Blueprint,
    initial: Part,
    ctx: Context,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> Product:
    """Execute *bp* starting from *initial*, returning the finished Product."""
    return await _Run(bp, initial, ctx, concurrency).execute()
