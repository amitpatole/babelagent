"""Contract tests from the adversarial repo review (scheduler/graph/topology)."""

from __future__ import annotations

import pytest

from babelagent import Grade, Graph
from babelagent.core.errors import TopologyError

_UNIFORM_KEYS = frozenset({"node", "state", "verdict", "reason", "elapsed_ms", "errored"})


def _boom(_):
    raise RuntimeError("branch down")


# --- verdict folds a tolerated crash (R1-1 / A4 / C4) -----------------------

async def test_tolerated_crash_surfaces_as_warn_not_pass():
    g = Graph()
    g.node("src", lambda n: n)
    g.node("ok", lambda n: n + 1, after=["src"])
    g.node("bad", _boom, after=["src"])
    g.join("j", after=["ok", "bad"], barrier="k_of_n", k=1, agent=lambda d: d)
    result = await g.run(1)
    assert result.ok is True          # k_of_n tolerated the crash
    assert result.verdict == "warn"   # ...but it is NOT reported as a clean pass


async def test_verdict_warn_passthrough():
    def warn_check(message, ctx):
        return Grade.warn("borderline")

    result = await Graph().node("x", lambda v: v, check=warn_check, gate="warn").run(1)
    assert result.ok is True and result.verdict == "warn" and result.output == 1


# --- optional barrier (R1-2) ------------------------------------------------

async def test_optional_skips_when_no_upstream_survives():
    g = Graph()
    g.node("src", lambda n: n)
    g.node("a", _boom, after=["src"])
    g.node("b", _boom, after=["src"])
    g.join("j", after=["a", "b"], barrier="optional", agent=lambda d: d)
    result = await g.run(1)
    states = {r["node"]: r["state"] for r in result.trace}
    assert states["j"] == "skipped"


async def test_optional_proceeds_with_survivors_only():
    g = Graph()
    g.node("src", lambda n: n)
    g.node("a", lambda n: n + 1, after=["src"])
    g.node("b", _boom, after=["src"])
    g.join("j", after=["a", "b"], barrier="optional", agent=lambda d: d)
    result = await g.run(1)
    assert result.output == {"a": 2}   # only the survivor


# --- duplicate dependency rejected (R1-3) -----------------------------------

def test_duplicate_dependency_rejected():
    g = Graph()
    g.node("a", lambda n: n)
    g.node("b", lambda n: n, after=["a", "a"], barrier="k_of_n", k=2)
    with pytest.raises(TopologyError, match="duplicate"):
        g.compile()


# --- deterministic trace order (R1-4) ---------------------------------------

async def test_trace_order_is_deterministic_across_runs():
    orders = set()
    for _ in range(15):
        g = Graph()
        g.node("src", lambda n: n)
        g.node("aaa", lambda n: n, after=["src"])
        g.node("bbb", lambda n: n, after=["src"])
        g.join("zzz", after=["aaa", "bbb"], agent=lambda d: d)
        result = await g.run(1)
        orders.add(tuple(r["node"] for r in result.trace))
    assert len(orders) == 1  # stable, not set-iteration-order dependent


# --- uniform trace record schema (A5 / C5) ----------------------------------

async def test_trace_records_have_uniform_keys():
    g = Graph()
    g.node("a", lambda n: n)
    g.node("bad", _boom, after=["a"])
    g.node("after_bad", lambda n: n, after=["bad"])  # skipped
    result = await g.run(1)
    assert {frozenset(r) for r in result.trace} == {_UNIFORM_KEYS}


# --- empty graph rejected (R1-5 / missing-test #7) --------------------------

def test_empty_graph_rejected():
    with pytest.raises(TopologyError, match="no nodes"):
        Graph().compile()


# --- CompiledGraph reuse is isolated (missing-test #8) ----------------------

async def test_compiled_graph_reuse_is_isolated():
    cg = Graph().node("u", str.upper).compile()
    r1 = await cg.run("a")
    r2 = await cg.run("b")
    assert r1.output == "A" and r2.output == "B"
    assert len(r1.trace) == 1 and len(r2.trace) == 1  # no cross-run accumulation


# --- per-resource concurrency (community feedback: local sequential / cloud parallel) ---

def _make_busy_tracker():
    active = {"now": 0, "max": 0}

    async def busy(x):
        import asyncio

        active["now"] += 1
        active["max"] = max(active["max"], active["now"])
        await asyncio.sleep(0.05)
        active["now"] -= 1
        return x

    return active, busy


async def test_resource_limit_serializes_nodes():
    active, busy = _make_busy_tracker()
    g = Graph()
    g.node("src", lambda n: n)
    g.node("a", busy, after=["src"], resource="local")
    g.node("b", busy, after=["src"], resource="local")
    g.join("j", after=["a", "b"], agent=lambda d: d)
    await g.run(1, resource_limits={"local": 1})
    assert active["max"] == 1  # the two 'local' nodes never overlapped


async def test_same_graph_runs_parallel_with_a_higher_limit():
    active, busy = _make_busy_tracker()
    g = Graph()
    g.node("src", lambda n: n)
    g.node("a", busy, after=["src"], resource="cloud")
    g.node("b", busy, after=["src"], resource="cloud")
    g.join("j", after=["a", "b"], agent=lambda d: d)
    await g.run(1, resource_limits={"cloud": 4})
    assert active["max"] == 2  # both ran concurrently (only two nodes)
