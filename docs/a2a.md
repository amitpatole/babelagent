# Agent-to-agent (A2A & MCP)

Babelagent's position on the agent-interop protocols is deliberate: **consume them, do not compete with
them.** Protocols like Google's A2A, the Model Context Protocol (MCP), and IBM's ACP are wire protocols
for (often remote) agents and tools to talk. They live at a different layer from an in-process
adapter-and-graph library. Babelagent treats a remote A2A agent or an MCP server as *just another
node*, so it sits on top of and between the standards.

## Consume a remote A2A agent

Point at an agent's base URL and it becomes a node other agents can hand messages to. Built on httpx
(base wheel, no extra), SSRF-guarded.

```python
from babelagent import Graph, A2ARef

g = (
    Graph()
    .node("triage", A2ARef("https://partner.example/agent"))   # a remote A2A agent
    .node("finalize", my_local_agent)
)
result = await g.run(ticket)
```

`A2AAgent` calls the agent's `message/send` method and can discover its Agent Card. A card whose `url`
points at an internal address is re-blocked by the SSRF guard.

## Consume an MCP tool

```python
from babelagent import Graph, McpRef

g = Graph().node("search", McpRef(command=["my-mcp-server"], tool="web_search"))
```

Requires `pip install "babelagent[mcp]"`.

## Expose a graph as an MCP server

The mirror image: let any MCP client (Claude, Cursor, another agent) run a whole graph as a tool.

```bash
babelagent mcp        # serves the demo graph over stdio as run_graph / graph_topology
```

```python
from babelagent.io.mcp import build_server
server = build_server(my_graph, name="my-pipeline")
server.run()
```

## Serve a graph over HTTP

```bash
babelagent serve --host 127.0.0.1 --port 8099
# POST /run {"payload": ...}  ·  GET /graph  ·  GET /health
```

The REST service is hardened from birth (constant-time auth, fail-closed off-loopback, body caps,
deadline clamp + guillotine, anti-DNS-rebind Host pinning). See [Security](SECURITY.md) for the full
posture and deployment guidance.

## How this differs from `any-agent`

The honest one-liner: mozilla.ai's `any-agent` gives you one interface across several agent frameworks;
Babelagent adds a **gated graph** so heterogeneous agents collaborate *and get graded at each hop*. A
sensible future move is to interoperate rather than reimplement: wrap an `any-agent` object as one more
adapter. See [the whole story](STORY.md) for the full landscape.
