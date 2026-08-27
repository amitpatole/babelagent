"""Topology validation: cycles, dangling deps, barrier arity."""

from __future__ import annotations

import pytest

from babelagent import Graph
from babelagent.core.errors import CycleError, TopologyError
from babelagent.core.node import BarrierKind, BarrierPolicy, Node
from babelagent.core.topology import Topology


class _Noop:
    def __init__(self, name):
        self.name = name

    async def run(self, message, ctx):
        return message


def _node(name, after=None, barrier=None):
    return Node(
        name=name,
        agent=_Noop(name),
        after=after or [],
        barrier=barrier or BarrierPolicy(),
    )


def test_dangling_dependency_rejected():
    topo = Topology(nodes={"a": _node("a", after=["missing"])})
    with pytest.raises(TopologyError, match="unknown node"):
        topo.validate()


def test_self_cycle_rejected():
    topo = Topology(nodes={"a": _node("a", after=["a"])})
    with pytest.raises(CycleError):
        topo.validate()


def test_two_node_cycle_rejected():
    topo = Topology(
        nodes={
            "a": _node("a", after=["b"]),
            "b": _node("b", after=["a"]),
        }
    )
    with pytest.raises(CycleError, match="cycle"):
        topo.validate()


def test_k_of_n_arity_validated():
    topo = Topology(
        nodes={
            "a": _node("a"),
            "b": _node("b", after=["a"], barrier=BarrierPolicy(kind=BarrierKind.K_OF_N, k=5)),
        }
    )
    with pytest.raises(TopologyError, match="k="):
        topo.validate()


def test_roots_and_terminals():
    g = Graph()
    g.node("a", lambda x: x)
    g.node("b", lambda x: x, after=["a"])
    g.node("c", lambda x: x, after=["a"])
    spec = g.compile().spec()
    assert spec["roots"] == ["a"]
    assert set(spec["terminals"]) == {"b", "c"}
