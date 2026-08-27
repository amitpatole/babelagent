# Adapters and `adapt()`

The "bring your own" machinery. `adapt(obj)` looks at whatever you hand it and returns a uniform
`Agent`. You rarely call it directly: `Graph().node(name, obj)` adapts `obj` for you.

## What can be adapted

| You bring | Becomes | Install |
|---|---|---|
| a Python callable (sync or async) | `CallableAgent` | base |
| an `http(s)` URL / OpenAPI doc | `HttpAgent` | base |
| a remote A2A agent (`A2ARef`) | `A2AAgent` | base |
| an MCP tool (`McpRef`) | `McpAgent` | `[mcp]` |
| a LangChain / CrewAI / AutoGen agent | framework adapter | `[frameworks]` |
| an LLM (`LLM("claude-opus-4-8", ...)`) | `LLM` | `[cloud]` / `[ollama]` |
| anything already shaped like `Agent` | itself, untouched | base |

```python
from babelagent import Graph, adapt

g = Graph()
g.node("clean",   str.strip)                                  # callable
g.node("classify", "https://api.example.com/classify", after=["clean"])   # HTTP
g.node("summary",  adapt(my_langchain_runnable), after=["clean"])          # framework agent
```

## Resolution order

`adapt()` tries, in order: already-an-Agent → custom/entry-point adapters → MCP ref → A2A ref →
framework agents (detected by module name, without importing the framework) → HTTP/OpenAPI → plain
callable (the universal fallback). Most specific first; the broad callable fallback last.

## Callables: how the payload maps to arguments

- 0 or 1 parameter → `fn(payload)`
- a dict payload whose keys **exactly** match the callable's required params → `fn(**payload)`
- a list/tuple whose length **exactly** fills the required positional params → `fn(*payload)`
- otherwise → `fn(payload)`

The exact-match rule is a safety boundary: a payload can come from an untrusted upstream agent, so it
is never allowed to inject keyword or positional "flag" arguments (`admin=True`) it wasn't meant to.
Sync callables run in a worker thread so they never block the event loop.

## HTTP and OpenAPI

`HttpAgent` posts the payload as JSON and returns the response. `HttpAgent.from_openapi(spec)` reads an
OpenAPI document (URL or dict) to learn how to call a service. The OpenAPI path only **reads** the
schema; it never fetches or executes remote code. All outbound URLs are SSRF-guarded (see
[Security](SECURITY.md)).

## LLMs

```python
from babelagent import Graph
from babelagent.adapters import LLM

g = Graph().node("draft", LLM("claude-opus-4-8", prompt="Summarize: {input}"))
```

Keys are read from the environment only. Defaults to the latest Claude model.

## Extending: register your own adapter

Teach `adapt()` a new kind of object without changing Babelagent, in-process or from another package.

```python
from babelagent import register_adapter

register_adapter(
    "my-thing",
    matches=lambda o: isinstance(o, MyThing),
    build=lambda o, **kw: MyThingAgent(o),
)
```

Across packages, declare an entry point in the `babelagent.adapters` group; Babelagent discovers it the
first time `adapt()` runs.

!!! warning "Plugins run code and take dispatch priority"
    Entry-point discovery is **on by default** and **runs the installed plugin's module code** the
    first time `adapt()` is called. Registered adapters (in-process *and* from plugins) are tried
    **before** every built-in, so a plugin whose `matches()` returns `True` for everything can hijack
    adaptation of any object and observe every adapted value. This is standard Python plugin behavior,
    but it is a supply-chain trust boundary: **trust your installed dependency set.** In locked-down
    environments set `BABELAGENT_NO_PLUGINS=1` to disable entry-point discovery entirely.
