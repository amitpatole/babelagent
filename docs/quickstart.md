# Quickstart

## Install

```bash
pip install babelagent
```

The base install is light (Pydantic, httpx, Typer). Heavy integrations live behind extras and are
imported only when used.

## A linear graph

Each `.node(name, agent)` runs after the previous one and hands it its message.

```python
import asyncio
from babelagent import Graph

async def main():
    graph = (
        Graph()
        .node("clean",   str.strip)
        .node("shout",   str.upper)
        .node("exclaim", lambda s: s + "!")
    )
    result = await graph.run("  hello  ")
    print(result.output)   # "HELLO!"
    print(result.ok, result.verdict)   # True pass

asyncio.run(main())
```

You never imported an `Agent` class. `adapt()` wrapped each callable for you. See
[Adapters](adapters.md).

## Branch, run in parallel, and join

Pass `after=[...]` and you are drawing a graph. Independent nodes run concurrently.

**Input shape (a contract):** a `.join()` **always** receives a dict keyed by the (surviving) upstream
node names, even for a single upstream, because it is an explicit fan-in. A plain `.node()` with one
declared upstream receives that message unwrapped (a linear hand-off); with two or more it also gets
the keyed dict. The type never flips based on which branch ran, so a join agent's input is stable.

```python
g = Graph()
g.node("src",    lambda n: n)
g.node("double", lambda n: n * 2, after=["src"])
g.node("square", lambda n: n * n, after=["src"])
g.join("sum", after=["double", "square"], agent=lambda d: d["double"] + d["square"])

result = await g.run(3)   # double=6, square=9 -> 15
```

Fan-in `barrier` policies control the join: `all` (every upstream must succeed), `k_of_n` (at least
`k`), or `optional` (proceed with whoever succeeded; the node is skipped if none did).

!!! note "Tolerated branches are absent from the dict"
    Under `k_of_n` / `optional`, the join dict contains only the **surviving** upstreams' keys, so a
    tolerated failure means its key is missing. Write join agents defensively (`d.get("x")`), not
    `d["x"]`. A run that tolerated a crashed branch reports `ok=True` but `verdict="warn"` (never a
    clean `pass`), and the crashed node appears in `result.trace`.

## Grade each hop

Any node can carry a `check` that returns a `Grade` of pass, warn, or fail. A `gate` mode decides what
that does: `off` (advisory), `warn` (block on fail), or `strict` (block on warn or fail). This is the
part nothing else ships.

```python
from babelagent import Graph, Grade

def nonempty(message, ctx):
    payload = message.payload
    return Grade.passed() if isinstance(payload, str) and payload.strip() else Grade.failed("empty")

g = Graph().node("summarize", my_summarizer, check=nonempty, gate="warn")
result = await g.run(text)
# if the summarizer returns "" the gate blocks: result.ok is False, verdict "fail"
```

## Try it with no API key

```console
$ babelagent demo
Babelagent demo — one agent, a quality gate, no API key.

broken graph → verdict=fail ok=False
  summarize: gate blocked: output is empty

fixed graph  → verdict=pass ok=True
  result: [24 words] Different agents speak different dialects, and Babelagent gives…

$ babelagent doctor
babelagent doctor
  ✓ babelagent                   version 0.1.0
  ✓ core deps (pydantic, httpx, typer) base wheel
  ✓ callable + HTTP + A2A adapters base wheel (no extra)
  ✓ MCP adapter + MCP server     available
  · Anthropic LLM                install babelagent[cloud]
```

`babelagent inspect` prints a graph's topology as JSON.

Next: [Adapters & `adapt()`](adapters.md) · [Agent-to-agent](a2a.md) · [Security](SECURITY.md).
