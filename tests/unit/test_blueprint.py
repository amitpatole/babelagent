"""Topology validation: cycles, dangling deps, barrier arity."""

from __future__ import annotations

import pytest

from byoa import Factory
from byoa.core.blueprint import BarrierPolicy, Blueprint, Node
from byoa.core.errors import BlueprintError, CycleError
from byoa.core.station import Station


def _station(name):
    return Station(name=name, agent=_Noop(name))


class _Noop:
    def __init__(self, name):
        self.name = name

    async def run(self, part, ctx):
        return part


def test_dangling_dependency_rejected():
    bp = Blueprint(nodes={"a": Node(station=_station("a"), after=["missing"])})
    with pytest.raises(BlueprintError, match="unknown station"):
        bp.validate()


def test_self_cycle_rejected():
    bp = Blueprint(nodes={"a": Node(station=_station("a"), after=["a"])})
    with pytest.raises(CycleError):
        bp.validate()


def test_two_node_cycle_rejected():
    bp = Blueprint(
        nodes={
            "a": Node(station=_station("a"), after=["b"]),
            "b": Node(station=_station("b"), after=["a"]),
        }
    )
    with pytest.raises(CycleError, match="cycle"):
        bp.validate()


def test_k_of_n_arity_validated():
    from byoa.core.blueprint import BarrierKind

    bp = Blueprint(
        nodes={
            "a": Node(station=_station("a")),
            "b": Node(
                station=_station("b"),
                after=["a"],
                barrier=BarrierPolicy(kind=BarrierKind.K_OF_N, k=5),
            ),
        }
    )
    with pytest.raises(BlueprintError, match="k="):
        bp.validate()


def test_roots_and_terminals():
    f = Factory()
    f.station("a", lambda x: x)
    f.station("b", lambda x: x, after=["a"])
    f.station("c", lambda x: x, after=["a"])
    line = f.compile()
    spec = line.spec()
    assert spec["roots"] == ["a"]
    assert set(spec["terminals"]) == {"b", "c"}
