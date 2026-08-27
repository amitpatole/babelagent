"""``babelagent`` command-line interface."""

from __future__ import annotations

import asyncio
import json

import typer

app = typer.Typer(
    add_completion=False,
    help="Babelagent — one common tongue for agents that were never meant to talk.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed Babelagent version."""
    from .. import __version__

    typer.echo(__version__)


@app.command()
def doctor() -> None:
    """Report which optional adapter families are available."""
    from .doctor import format_checks, run_checks

    typer.echo("babelagent doctor")
    typer.echo(format_checks(run_checks()))


@app.command()
def demo() -> None:
    """Run a key-free demo: a broken graph (gated FAIL) then a fixed graph (PASS)."""
    from ._demo_assets import DEMO_TEXT, build_broken, build_fixed

    typer.echo("Babelagent demo — one agent, a quality gate, no API key.\n")
    typer.echo(f"input: {DEMO_TEXT}\n")

    broken = asyncio.run(build_broken().run(DEMO_TEXT))
    typer.secho(f"broken graph → verdict={broken.verdict} ok={broken.ok}",
                fg=typer.colors.RED)
    typer.echo(f"  {_last_reason(broken)}\n")

    fixed = asyncio.run(build_fixed().run(DEMO_TEXT))
    typer.secho(f"fixed graph  → verdict={fixed.verdict} ok={fixed.ok}",
                fg=typer.colors.GREEN)
    typer.echo(f"  result: {fixed.output}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host (non-loopback requires a token)."),
    port: int = typer.Option(8099, help="Bind port."),
) -> None:
    """Serve the demo graph over HTTP (requires the `serve` extra)."""
    from ._demo_assets import build_fixed
    from .rest import serve as _serve

    typer.echo(f"babelagent serve → http://{host}:{port} (POST /run)")
    _serve(build_fixed(), host=host, port=port)


@app.command()
def mcp() -> None:
    """Expose the demo graph as an MCP server over stdio (requires the `mcp` extra)."""
    from ._demo_assets import build_fixed
    from .mcp import build_server

    build_server(build_fixed()).run()


@app.command()
def inspect() -> None:
    """Print the demo graph's topology as JSON."""
    from ._demo_assets import build_fixed

    graph = build_fixed().compile()
    typer.echo(json.dumps(graph.spec(), indent=2))


def _last_reason(result) -> str:  # type: ignore[no-untyped-def]
    for record in reversed(result.trace):
        if record.get("reason"):
            return f"{record['node']}: {record['reason']}"
    return "(no issues recorded)"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
