# Babelagent

[![PyPI](https://img.shields.io/pypi/v/babelagent.svg)](https://pypi.org/project/babelagent/)
[![Docs](https://img.shields.io/badge/docs-live-3f8a86)](https://amitpatole.github.io/babelagent/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22129957.svg)](https://doi.org/10.5281/zenodo.22129957)
[![License: MIT](https://img.shields.io/badge/license-MIT-1b1a17)](LICENSE)

> The Babel that lets AI agents understand each other. One shared tongue for agents that were never meant to talk.

Every agent framework has its own idea of what an agent is. LangChain has Runnables with `.invoke`,
CrewAI has Crews with `.kickoff`, AutoGen has agents with `.generate_reply`, an LLM has
`messages.create`, a microservice has an HTTP route. None of them agree on a shape, so connecting any
two means writing glue.

Babelagent is the neutral layer in between. You bring your own agents, whatever they are (a callable,
an HTTP/OpenAPI endpoint, an MCP tool, a framework agent, or an LLM), and it wraps each one in a single
shared interface so they can exchange messages and collaborate on a task, **agent-to-agent (A2A)**.
The value is not any single adapter. It is that once something is adapted, it works with everything
else you have adapted.

The headline is **`adapt()`**: hand Babelagent almost anything and it builds the connector on the fly.

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

Let different agents work in parallel and hand their results to each other, with barrier policies on
the join:

```python
g = Graph()
g.node("src",     lambda text: text)
g.node("summary", adapt(langchain_agent), after=["src"])   # a LangChain agent
g.node("labels",  adapt("https://api.example.com/classify"), after=["src"])  # an HTTP service
g.join("merge", after=["summary", "labels"], agent=combine, barrier="all")
result = await g.run(document)
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

## Install

```bash
pip install babelagent                 # light base (callables + HTTP)
pip install "babelagent[mcp]"          # MCP tools
pip install "babelagent[cloud]"        # Anthropic / OpenAI
pip install "babelagent[ollama]"       # local models
pip install "babelagent[frameworks]"   # LangChain / CrewAI / AutoGen
pip install "babelagent[serve]"        # REST service
pip install "babelagent[all]"
```

## Try it (no API key)

```bash
babelagent demo      # a broken agent (gated FAIL) then a fixed one (PASS)
babelagent doctor    # which adapter families are available
babelagent inspect   # print a graph's topology as JSON
```

## Cite

If you use Babelagent, please cite it (concept DOI, always resolves to the latest version):

> Amit Patole. *Babelagent*. https://doi.org/10.5281/zenodo.22129957

A machine-readable `CITATION.cff` is in the repo.

## Status

Alpha, in active development. MIT licensed.

— amitpatole
