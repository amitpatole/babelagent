"""``byoa`` command-line interface."""

from __future__ import annotations

import asyncio
import json

import typer

app = typer.Typer(
    add_completion=False,
    help="BYOA — Bring Your Own Agent. A factory with an assembly line.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed BYOA version."""
    from .. import __version__

    typer.echo(__version__)


@app.command()
def doctor() -> None:
    """Report which optional adapter families are available."""
    from .doctor import format_checks, run_checks

    typer.echo("byoa doctor")
    typer.echo(format_checks(run_checks()))


@app.command()
def demo() -> None:
    """Run a key-free demo: a broken line (gated FAIL) then a fixed line (PASS)."""
    from ._demo_assets import DEMO_TEXT, build_broken, build_fixed

    typer.echo("BYOA demo — one station, a quality gate, no API key.\n")
    typer.echo(f"input: {DEMO_TEXT}\n")

    broken = asyncio.run(build_broken().run(DEMO_TEXT))
    typer.secho(f"broken line → verdict={broken.verdict} ok={broken.ok}",
                fg=typer.colors.RED)
    typer.echo(f"  {_last_reason(broken)}\n")

    fixed = asyncio.run(build_fixed().run(DEMO_TEXT))
    typer.secho(f"fixed line  → verdict={fixed.verdict} ok={fixed.ok}",
                fg=typer.colors.GREEN)
    typer.echo(f"  product: {fixed.output}")


@app.command()
def inspect(
    blueprint: str | None = typer.Argument(
        None, help="Path to a Python file exposing a `line` Factory/Line (optional)."
    ),
) -> None:
    """Print the topology of the demo line (or a line from a file)."""
    if blueprint is None:
        from ._demo_assets import build_fixed

        line = build_fixed().compile()
        typer.echo(json.dumps(line.spec(), indent=2))
        return
    typer.secho("Loading a line from a file is not wired yet.", fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)


def _last_reason(product) -> str:  # type: ignore[no-untyped-def]
    for record in reversed(product.trace):
        if record.get("reason"):
            return f"{record['station']}: {record['reason']}"
    return "(no issues recorded)"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
