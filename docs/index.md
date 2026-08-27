# Babelagent

**The Babel that lets AI agents understand each other.** One shared tongue for agents that were never
meant to talk.

Every agent framework has its own idea of what an agent is. LangChain has Runnables with `.invoke`,
CrewAI has Crews with `.kickoff`, AutoGen has agents with `.generate_reply`, an LLM has
`messages.create`, a microservice has an HTTP route. None of them agree on a shape, so connecting any
two means writing glue.

Babelagent is the neutral layer in between. You bring your own agents, whatever they are, and it wraps
each one in a single shared interface so they can exchange messages and collaborate on a task,
**agent-to-agent (A2A)**, and get graded at each hop.

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

asyncio.run(main())
```

## Why it exists

Existing frameworks each want to *be* your world: adopt our agent model, our memory, our orchestration.
Two of them in one process fight rather than cooperate. Babelagent owns very little on purpose. It is
not another framework; it is the shared tongue between them, the wiring that carries messages, and an
inspector that grades each hop before it continues.

The one thing it does that nothing else ships: **a per-hop, tri-state quality gate (pass / warn / fail)
that can stop bad output from flowing downstream, on a framework-agnostic agent graph.** See
[the whole story](STORY.md) for the honest landscape (what is commodity, what is the wedge, and how it
sits *on top of* A2A/MCP rather than against them).

## Install

```bash
pip install babelagent                 # light base (callables + HTTP + A2A)
pip install "babelagent[mcp]"          # MCP tools + MCP server
pip install "babelagent[cloud]"        # Anthropic / OpenAI
pip install "babelagent[frameworks]"   # LangChain (CrewAI/AutoGen detected if installed)
pip install "babelagent[serve]"        # REST service
pip install "babelagent[all]"
```

## Try it (no API key)

```console
$ babelagent demo
Babelagent demo — one agent, a quality gate, no API key.

broken graph → verdict=fail ok=False
  summarize: gate blocked: output is empty

fixed graph  → verdict=pass ok=True
  result: [24 words] Different agents speak different dialects, and Babelagent gives…
```

## Concepts

| Concept | What it is |
|---|---|
| **Graph** | Builds the network of agents (linear chaining **and** a DAG API) |
| **CompiledGraph** | The validated, runnable graph; `await graph.run(payload)` |
| **Node** | One participant: an agent plus an optional quality check/gate |
| **Agent** | The uniform `async run(message, ctx) -> message` interface |
| **`adapt()`** | Turns any brought object into an Agent, inferring the adapter |
| **Message / Result** | The envelope agents exchange / the final output + run trace |
| **Barrier** | Fan-in join policy: `all` · `k_of_n` · `optional` |

Next: the [Quickstart](quickstart.md), the [adapters guide](adapters.md), and
[agent-to-agent](a2a.md).

## Cite

Concept DOI (always resolves to the latest version):
[10.5281/zenodo.22129957](https://doi.org/10.5281/zenodo.22129957).

*— amitpatole*
