"""The key-free demo behaves as documented: broken FAILs, fixed PASSes."""

from __future__ import annotations

from babelagent.io._demo_assets import DEMO_TEXT, build_broken, build_fixed


async def test_broken_graph_fails_gate():
    result = await build_broken().run(DEMO_TEXT)
    assert not result.ok
    assert result.verdict == "fail"


async def test_fixed_graph_passes_and_produces():
    result = await build_fixed().run(DEMO_TEXT)
    assert result.ok
    assert result.verdict == "pass"
    assert isinstance(result.output, str) and result.output.startswith("[")


def test_doctor_runs():
    from babelagent.io.doctor import format_checks, run_checks

    checks = run_checks()
    assert any(c.name == "babelagent" and c.ok for c in checks)
    assert isinstance(format_checks(checks), str)
