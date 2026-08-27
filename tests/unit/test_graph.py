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
    # only the surviving upstream contributes; a single contributor is unwrapped
    assert result.output == 11


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
