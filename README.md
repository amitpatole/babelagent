# BYOA — Bring Your Own Agent

> A factory with an assembly line. Bring any agent, plug it onto a station, run the line, produce what you want.

BYOA is a lightweight, framework-agnostic SDK for composing heterogeneous agents into a verifiable
production line. The SDK is the **factory**; you bring your own agents — any callable, HTTP/OpenAPI
endpoint, MCP tool, framework agent (LangChain / CrewAI / AutoGen), or LLM — and plug each one onto a
**station**. The line runs them and hands you a **product**, with an optional quality **gate** at every
station.

The headline is **`adapt()`**: hand BYOA almost anything and it builds the connector on the fly.

```python
import asyncio
from byoa import Factory

async def main():
    line = (
        Factory()
        .station("clean",     str.strip)
        .station("shout",     str.upper)
        .station("exclaim",   lambda s: s + "!")
    )
    product = await line.run("  hello  ")
    print(product.output)   # "HELLO!"

asyncio.run(main())
```

Branch, run in parallel, and join with barrier policies:

```python
f = Factory()
f.station("src",    lambda n: n)
f.station("double", lambda n: n * 2, after=["src"])
f.station("square", lambda n: n * n, after=["src"])
f.join("sum", after=["double", "square"], agent=lambda d: d["double"] + d["square"])
product = await f.run(3)   # 6 + 9 == 15
```

## Concepts

| Concept | What it is |
|---|---|
| **Factory** | Builder that assembles a line (linear sugar **and** a DAG API) |
| **Line** | The compiled, validated assembly line; `await line.run(payload)` |
| **Station** | One node: an agent + an optional quality check/gate |
| **Agent** | The uniform `async run(part, ctx) -> part` worker interface |
| **`adapt()`** | Turns any brought object into an Agent, inferring the adapter |
| **Part / Product** | The envelope on the belt / the finished output + run trace |
| **Barrier** | Fan-in join policy: `all` · `k_of_n` · `optional` |

## Install

```bash
pip install byoa-sdk                 # light base wheel (callables + HTTP)
pip install "byoa-sdk[mcp]"          # MCP tools
pip install "byoa-sdk[cloud]"        # Anthropic / OpenAI
pip install "byoa-sdk[ollama]"       # local models
pip install "byoa-sdk[frameworks]"   # LangChain / CrewAI / AutoGen
pip install "byoa-sdk[serve]"        # REST service
pip install "byoa-sdk[all]"
```

## Try it (no API key)

```bash
byoa demo      # a broken station (gated FAIL) then a fixed one (PASS)
byoa doctor    # which adapter families are available
byoa inspect   # print a line's topology as JSON
```

## Status

Alpha, in active development. Local-only for now. MIT licensed.

— amitpatole
