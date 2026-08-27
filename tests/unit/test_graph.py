"""Core graph behaviour: linear chains, DAGs, barriers, gates."""

from __future__ import annotations

import pytest

from babelagent import GateMode, Graph, Message, Verdict
from babelagent.core.agent import Context, IdentityAgent
from babelagent.core.grade import Grade


async def test_linear_three_nodes():
    result = await (
        Graph()
        .node("a", lambda s: s + "-a")
        .node("b", lambda s: s + "-b")
        .node("c", lambda s: s + "-c")
        .run("x")
    )
    assert result.ok
    assert result.output == "x-a-b-c"
    assert [r["node"] for r in result.trace] == ["a", "b", "c"]


async def test_fanout_join_dag():
    g = Graph()
    g.node("src", lambda n: n)
    g.node("double", lambda n: n * 2, after=["src"])
    g.node("square", lambda n: n * n, after=["src"])
    g.join("sum", after=["double", "square"], agent=lambda d: d["double"] + d["square"])
    result = await g.run(3)
    assert result.ok
    assert result.output == 6 + 9  # double=6, square=9


async def test_k_of_n_barrier_proceeds_on_partial():
    def boom(_):
        raise RuntimeError("agent down")

    g = Graph()
    g.node("src", lambda n: n)
    g.node("ok", lambda n: n + 1, after=["src"])
    g.node("bad", boom, after=["src"])
    # join needs only 1 of its 2 upstreams to succeed
    g.join("gather", after=["ok", "bad"], barrier="k_of_n", k=1, agent=lambda d: d)
    result = await g.run(10)
    assert result.ok  # 'ok' succeeded, satisfying k=1
    # SHAPE CONTRACT: a join with >=2 declared upstreams ALWAYS gets a dict keyed
    # by the survivors, even when only one survived. The type never flips to bare.
    assert result.output == {"ok": 11}


async def test_join_shape_is_stable_whether_or_not_a_sibling_flakes():
    """The both-succeed and one-flaked cases hand the join agent the same TYPE."""

    def boom(_):
        raise RuntimeError("down")

    def both():
        g = Graph()
        g.node("src", lambda n: n)
        g.node("a", lambda n: n + 1, after=["src"])
        g.node("b", lambda n: n + 2, after=["src"])
        g.join("j", after=["a", "b"], barrier="k_of_n", k=1, agent=lambda d: d)
        return g

    def one_flakes():
        g = Graph()
        g.node("src", lambda n: n)
        g.node("a", lambda n: n + 1, after=["src"])
        g.node("b", boom, after=["src"])
        g.join("j", after=["a", "b"], barrier="k_of_n", k=1, agent=lambda d: d)
        return g

    r_both = await both().run(10)
    r_one = await one_flakes().run(10)
    # Both are dicts (never a bare value); only the present keys differ.
    assert r_both.output == {"a": 11, "b": 12}
    assert r_one.output == {"a": 11}
    assert isinstance(r_both.output, dict) and isinstance(r_one.output, dict)


async def test_all_barrier_skips_downstream_on_failure():
    def boom(_):
        raise ValueError("nope")

    g = Graph()
    g.node("a", lambda n: n, after=[])
    g.node("bad", boom, after=["a"])
    g.node("after_bad", lambda n: n, after=["bad"])  # ALL barrier → skipped
    result = await g.run(1)
    assert not result.ok
    states = {r["node"]: r["state"] for r in result.trace}
    assert states["bad"] == "failed"
    assert states["after_bad"] == "skipped"


async def test_gate_fail_blocks_and_marks_failed():
    def check_positive(message: Message, ctx: Context) -> Grade:
        return Grade.passed() if message.payload > 0 else Grade.failed("must be > 0")

    g = Graph().node("neg", lambda n: -n, check=check_positive, gate=GateMode.WARN)
    result = await g.run(5)
    assert not result.ok
    assert result.verdict == Verdict.FAIL.value


async def test_gate_off_is_advisory_only():
    def always_fail(message: Message, ctx: Context) -> Grade:
        return Grade.failed("advisory")

    g = Graph().node("x", lambda n: n, check=always_fail, gate="off")
    result = await g.run(1)
    assert result.ok  # advisory check never blocks
    assert result.output == 1


async def test_identity_join_default_agent():
    g = Graph()
    g.node("a", lambda n: n + 1)
    g.node("b", lambda n: n + 2, after=["a"])
    g.join("end", after=["b"])  # default IdentityAgent
    result = await g.run(0)
    assert result.output == 3


def test_duplicate_node_rejected():
    g = Graph().node("a", lambda x: x)
    with pytest.raises(ValueError, match="duplicate"):
        g.node("a", lambda x: x)


def test_identity_agent_is_agent():
    from babelagent import is_agent

    assert is_agent(IdentityAgent())


async def test_cancelling_a_run_cancels_inflight_nodes():
    """A client disconnect (run() cancelled) must cancel in-flight node tasks,
    not orphan them — a cooperative agent receives its CancelledError."""
    import asyncio

    got = {"cancelled": False}

    async def cooperative(x):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            got["cancelled"] = True
            raise

    task = asyncio.ensure_future(Graph().node("c", cooperative).run("x"))
    await asyncio.sleep(0.1)  # let the node start
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert got["cancelled"] is True  # the finally cancelled the in-flight node
