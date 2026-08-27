"""The key-free demo line behaves as documented: broken FAILs, fixed PASSes."""

from __future__ import annotations

from byoa.io._demo_assets import DEMO_TEXT, build_broken, build_fixed


async def test_broken_line_fails_gate():
    product = await build_broken().run(DEMO_TEXT)
    assert not product.ok
    assert product.verdict == "fail"


async def test_fixed_line_passes_and_produces():
    product = await build_fixed().run(DEMO_TEXT)
    assert product.ok
    assert product.verdict == "pass"
    assert isinstance(product.output, str) and product.output.startswith("[")


def test_doctor_runs():
    from byoa.io.doctor import format_checks, run_checks

    checks = run_checks()
    assert any(c.name == "byoa" and c.ok for c in checks)
    assert isinstance(format_checks(checks), str)
