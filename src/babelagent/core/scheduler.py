"""The async DAG executor: drives messages between agents in the graph.

Reactive scheduling: a node runs as soon as its barrier over upstreams is
satisfied; independent branches run concurrently under a bounded semaphore.
Failures (agent error, timeout, or a blocking gate) propagate through barriers,
skipping nodes that can no longer be satisfied.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .agent import Context
from .grade import Grade, Verdict
from .message import Message, Result
from .node import BarrierKind
from .topology import Topology

# Max concurrent node executions (a wide fan-out queues on the semaphore).
DEFAULT_CONCURRENCY = 8

# How long the cancellation cleanup waits for cooperative tasks to unwind before
# abandoning any that swallow cancellation (keeps the guillotine time-bounded).
_CLEANUP_GRACE_S = 0.25


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
    message: Message | None
    grade: Grade | None
    error: str | None
    elapsed_ms: int
    errored: bool = False  # True only for a genuine exception (its text is sensitive)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _record(
    node: str,
    state: str,
    *,
    verdict: str | None = None,
    reason: str = "",
    elapsed_ms: int = 0,
    errored: bool = False,
) -> dict[str, Any]:
    """A trace record with a UNIFORM key set (skipped/timeout rows included)."""
    return {
        "node": node,
        "state": state,
        "verdict": verdict,
        "reason": reason,
        "elapsed_ms": elapsed_ms,
        "errored": errored,
    }


class _Run:
    """Holds mutable state for a single graph execution."""

    def __init__(
        self,
        topo: Topology,
        initial: Message,
        ctx: Context,
        concurrency: int,
        resource_limits: dict[str, int] | None = None,
    ) -> None:
        self.topo = topo
        self.initial = initial
        self.ctx = ctx
        self.sem = asyncio.Semaphore(max(1, concurrency))
        # Per-resource semaphores: nodes tagged with the same `resource` share a
        # limit (e.g. a local model that must run sequentially -> {"local": 1}).
        self.resource_sems: dict[str, asyncio.Semaphore] = {
            name: asyncio.Semaphore(max(1, limit))
            for name, limit in (resource_limits or {}).items()
        }
        self.states: dict[str, NodeState] = {n: NodeState.PENDING for n in topo.nodes}
        self.outputs: dict[str, Message] = {}
        self.grades: dict[str, Grade] = {}
        self.records: list[dict[str, Any]] = []

    # --- barrier logic ----------------------------------------------------
    def _succeeded(self, ups: list[str]) -> list[str]:
        return [u for u in ups if self.states[u] is NodeState.DONE]

    def _settled(self, ups: list[str]) -> bool:
        return all(self.states[u] in _TERMINAL for u in ups)

    def barrier_ready(self, name: str) -> bool:
        node = self.topo.nodes[name]
        ups = node.after
        if not ups:
            return True
        kind = node.barrier.kind
        if kind is BarrierKind.ALL:
            return len(self._succeeded(ups)) == len(ups)
        if kind is BarrierKind.K_OF_N:
            return len(self._succeeded(ups)) >= (node.barrier.k or 1)
        # OPTIONAL: run once settled, provided at least one upstream succeeded
        # (otherwise there is nothing to hand the node — see barrier_impossible).
        return self._settled(ups) and len(self._succeeded(ups)) >= 1

    def barrier_impossible(self, name: str) -> bool:
        node = self.topo.nodes[name]
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
        # OPTIONAL: unsatisfiable only if everyone settled and none succeeded.
        return self._settled(ups) and len(succeeded) == 0

    # --- input gathering --------------------------------------------------
    def gather_input(self, name: str) -> Message:
        # Input SHAPE is a stable contract, decided by the node kind + the number
        # of DECLARED upstreams (never by how many survived):
        #   * a `.join()` node, or any node with >= 2 declared upstreams, ALWAYS
        #     receives a dict keyed by the surviving upstream names (even under
        #     k_of_n when only one survived);
        #   * a plain node with one declared upstream receives that message
        #     unwrapped (a linear hand-off).
        # So a join agent's input type never flips between a bare value and a dict.
        node = self.topo.nodes[name]
        if not node.after:
            return self.initial
        contributing = [
            u for u in node.after if self.states[u] is NodeState.DONE and u in self.outputs
        ]
        if len(node.after) == 1 and not node.join:
            return self.outputs[contributing[0]] if contributing else Message(payload=None)
        merged_payload = {u: self.outputs[u].payload for u in contributing}
        merged_meta: dict[str, Any] = {}
        for u in contributing:
            merged_meta.update(self.outputs[u].meta)
        return Message(payload=merged_payload, meta=merged_meta)

    # --- single node ------------------------------------------------------
    async def run_node(self, name: str) -> _Outcome:
        node = self.topo.nodes[name]
        message = self.gather_input(name)
        start = time.monotonic()

        timeout = _effective_timeout(node.timeout_s, self.ctx)
        # Acquire the per-resource semaphore FIRST (so a queued node doesn't hold
        # a global concurrency slot while it waits), then the global semaphore.
        res_sem = self.resource_sems.get(node.resource) if node.resource else None
        res_ctx: Any = res_sem if res_sem is not None else contextlib.nullcontext()
        async with res_ctx, self.sem:
            try:
                if timeout is not None and timeout <= 0:
                    raise TimeoutError
                coro = node.agent.run(message, self.ctx)
                out = await (asyncio.wait_for(coro, timeout) if timeout is not None else coro)
            except TimeoutError:
                return _Outcome(name, NodeState.FAILED, None, None, "node timed out", _ms(start))
            except Exception as exc:  # noqa: BLE001 — record any agent failure as a node failure
                # Full text kept in the local trace for debugging; marked
                # `errored` so network surfaces (REST/MCP) redact it.
                return _Outcome(
                    name, NodeState.FAILED, None, None,
                    f"{type(exc).__name__}: {exc}", _ms(start), errored=True,
                )

            grade: Grade | None = None
            if node.check is not None:
                try:
                    grade = await _maybe_await(node.check(out, self.ctx))
                except Exception as exc:  # noqa: BLE001 — class name only, no message (may leak internals)
                    grade = Grade.failed(f"check raised {type(exc).__name__}")
                if node.gate.blocks(grade.verdict):
                    return _Outcome(
                        name, NodeState.FAILED, out, grade,
                        f"gate blocked: {grade.reason}", _ms(start)
                    )
            return _Outcome(name, NodeState.DONE, out, grade, None, _ms(start))

    # --- driver -----------------------------------------------------------
    async def execute(self) -> Result:
        running: dict[str, asyncio.Task[_Outcome]] = {}
        try:
            while True:
                progressed = False

                # Mark nodes whose barrier can never be satisfied as skipped.
                for name in self.topo.nodes:
                    if self.states[name] is NodeState.PENDING and self.barrier_impossible(name):
                        self.states[name] = NodeState.SKIPPED
                        self.records.append(_record(
                            name, "skipped", reason="upstream barrier unsatisfiable"
                        ))
                        progressed = True

                # Launch every ready node. The semaphore in run_node bounds how
                # many run CONCURRENTLY; it does not bound task creation, so a
                # wide fan-out still creates one task per ready node. Graph size
                # is author-defined at build time (not attacker-driven over the
                # network, which only injects the payload into a compiled graph).
                for name in self.topo.nodes:
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
                    # Absorb in a deterministic (node-name) order so the trace is
                    # stable for siblings that complete in the same event-loop wake.
                    for outcome in sorted((t.result() for t in done), key=lambda o: o.name):
                        self._absorb(outcome)
                        running.pop(outcome.name, None)
                    continue

                if not progressed:
                    break

            return self._finish()
        finally:
            # On cancellation (the run guillotine, or a REST client disconnect)
            # cancel the in-flight node tasks so cooperative agents receive their
            # CancelledError. Wait only briefly for them to unwind, then abandon
            # any that swallow cancellation — otherwise awaiting a hostile agent
            # here would block past the guillotine's bound (the whole point of it).
            if running:
                for task in running.values():
                    task.cancel()
                await asyncio.wait(set(running.values()), timeout=_CLEANUP_GRACE_S)

    def _absorb(self, outcome: _Outcome) -> None:
        self.states[outcome.name] = outcome.state
        if outcome.message is not None:
            self.outputs[outcome.name] = outcome.message
        if outcome.grade is not None:
            self.grades[outcome.name] = outcome.grade
        self.records.append(_record(
            outcome.name,
            outcome.state.value,
            verdict=(outcome.grade.verdict.value if outcome.grade else None),
            reason=outcome.error or (outcome.grade.reason if outcome.grade else ""),
            elapsed_ms=outcome.elapsed_ms,
            errored=outcome.errored,
        ))

    def _finish(self) -> Result:
        # Same shape contract as gather_input: the result shape is decided by the
        # number of DECLARED terminals, not how many finished. One terminal -> its
        # payload, unwrapped; two or more -> always a dict keyed by the terminals
        # that completed. The return type never flips based on which branch flaked.
        terminals = self.topo.terminals()
        done_terminals = [t for t in terminals if self.states[t] is NodeState.DONE]
        if len(terminals) == 1:
            output: Any = self.outputs[done_terminals[0]].payload if done_terminals else None
        else:
            output = {t: self.outputs[t].payload for t in done_terminals}

        # The run succeeded if every terminal produced its output. A failure on a
        # branch that a downstream barrier (k_of_n / optional) tolerated is
        # recorded in the trace but does not, by itself, fail the result.
        ok = bool(terminals) and all(self.states[t] is NodeState.DONE for t in terminals)
        verdict = Verdict.worst([g.verdict for g in self.grades.values()])
        if not ok:
            verdict = Verdict.FAIL
        elif any(s is NodeState.FAILED for s in self.states.values()):
            # A tolerated branch crashed (no Grade of its own): surface it as at
            # least WARN so verdict==pass never hides an errored node.
            verdict = Verdict.worst([verdict, Verdict.WARN])
        return Result(output=output, ok=ok, verdict=verdict.value, trace=self.records)


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _effective_timeout(node_timeout: float | None, ctx: Context) -> float | None:
    rem = ctx.remaining()
    candidates = [t for t in (node_timeout, rem) if t is not None]
    return min(candidates) if candidates else None


async def run_topology(
    topo: Topology,
    initial: Message,
    ctx: Context,
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    resource_limits: dict[str, int] | None = None,
) -> Result:
    """Execute *topo* starting from *initial*, returning the final Result."""
    return await _Run(topo, initial, ctx, concurrency, resource_limits).execute()
