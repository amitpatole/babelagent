"""Core assembly-line behaviour: linear chains, DAGs, barriers, gates."""

from __future__ import annotations

import pytest

from byoa import Factory, GateMode, Part, Verdict
from byoa.core.agent import Context, IdentityAgent
from byoa.core.verdict import Result


async def test_linear_three_stations():
    product = await (
        Factory()
        .station("a", lambda s: s + "-a")
        .station("b", lambda s: s + "-b")
        .station("c", lambda s: s + "-c")
        .run("x")
    )
    assert product.ok
    assert product.output == "x-a-b-c"
    assert [r["station"] for r in product.trace] == ["a", "b", "c"]


async def test_fanout_join_dag():
    f = Factory()
    f.station("src", lambda n: n)
    f.station("double", lambda n: n * 2, after=["src"])
    f.station("square", lambda n: n * n, after=["src"])
    f.join("sum", after=["double", "square"], agent=lambda d: d["double"] + d["square"])
    product = await f.run(3)
    assert product.ok
    assert product.output == 6 + 9  # double=6, square=9


async def test_k_of_n_barrier_proceeds_on_partial():
    def boom(_):
        raise RuntimeError("station down")

    f = Factory()
    f.station("src", lambda n: n)
    f.station("ok", lambda n: n + 1, after=["src"])
    f.station("bad", boom, after=["src"])
    # join needs only 1 of its 2 upstreams to succeed
    f.join("gather", after=["ok", "bad"], barrier="k_of_n", k=1,
           agent=lambda d: d)
    product = await f.run(10)
    assert product.ok  # 'ok' succeeded, satisfying k=1
    # only the surviving upstream contributes; a single contributor is unwrapped
    assert product.output == 11


async def test_all_barrier_skips_downstream_on_failure():
    def boom(_):
        raise ValueError("nope")

    f = Factory()
    f.station("a", lambda n: n, after=[])
    f.station("bad", boom, after=["a"])
    f.station("after_bad", lambda n: n, after=["bad"])  # ALL barrier → skipped
    product = await f.run(1)
    assert not product.ok
    states = {r["station"]: r["state"] for r in product.trace}
    assert states["bad"] == "failed"
    assert states["after_bad"] == "skipped"


async def test_gate_fail_blocks_and_marks_failed():
    def check_positive(part: Part, ctx: Context) -> Result:
        return Result.passed() if part.payload > 0 else Result.failed("must be > 0")

    f = Factory().station("neg", lambda n: -n, check=check_positive, gate=GateMode.WARN)
    product = await f.run(5)
    assert not product.ok
    assert product.verdict == Verdict.FAIL.value


async def test_gate_off_is_advisory_only():
    def always_fail(part: Part, ctx: Context) -> Result:
        return Result.failed("advisory")

    f = Factory().station("x", lambda n: n, check=always_fail, gate="off")
    product = await f.run(1)
    assert product.ok  # advisory check never blocks
    assert product.output == 1


async def test_identity_join_default_agent():
    f = Factory()
    f.station("a", lambda n: n + 1)
    f.station("b", lambda n: n + 2, after=["a"])
    f.join("end", after=["b"])  # default IdentityAgent
    product = await f.run(0)
    assert product.output == 3


def test_duplicate_station_rejected():
    f = Factory().station("a", lambda x: x)
    with pytest.raises(ValueError, match="duplicate"):
        f.station("a", lambda x: x)


def test_identity_agent_is_agent():
    from byoa import is_agent

    assert is_agent(IdentityAgent())
