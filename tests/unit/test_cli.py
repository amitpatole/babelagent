"""CLI wiring tests (Typer CliRunner) — previously uncovered."""

from __future__ import annotations

from typer.testing import CliRunner

from babelagent.io.cli import app

runner = CliRunner()


def test_cli_version():
    import babelagent

    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0 and babelagent.__version__ in r.stdout


def test_cli_doctor():
    r = runner.invoke(app, ["doctor"])
    assert r.exit_code == 0 and "babelagent" in r.stdout


def test_cli_demo():
    r = runner.invoke(app, ["demo"])
    assert r.exit_code == 0 and "verdict=" in r.stdout


def test_cli_inspect():
    r = runner.invoke(app, ["inspect"])
    assert r.exit_code == 0 and "nodes" in r.stdout


def test_cli_no_args_shows_help():
    r = runner.invoke(app, [])
    # no_args_is_help prints usage and exits 2 (Typer convention) — not a crash
    assert r.exit_code == 2
    assert "Usage" in r.output
