# BYOA: The Whole Story

*A long-form explainer of what BYOA is, why it exists, how it is built, how things plug into it, and the tradeoffs behind every choice. Read it once and you should be able to stand at a whiteboard and explain the skeleton, then explain how anything a user brings clicks onto it.*

---

## 1. The premise, in one breath

BYOA stands for **Bring Your Own Agent**. The idea is simple enough to say in a sentence: the SDK is a **factory**, the pipeline you build with it is an **assembly line**, and the workers you drop onto that line are **agents you already have**. You bring the workers; BYOA gives you the belt, the stations, the quality gates, and the machinery that moves work from one end to the other and hands you a finished product. Nothing about the worker has to be written "for BYOA." A plain Python function, a web endpoint, a tool exposed over the Model Context Protocol, an agent built in LangChain or CrewAI, or a raw call to an LLM: each of these is just a worker, and BYOA's job is to make them all stand at the same kind of station and speak the same language while they do it.

That is the entire pitch. Everything else in this document is about why that pitch is worth building, and how the machine underneath makes it true without leaking its own opinions onto the agents you bring.

---

## 2. The problem it answers

If you have ever tried to wire two agent frameworks together, you already know the pain. Every framework has its own idea of what an "agent" is. LangChain has Runnables with `.invoke`. CrewAI has Crews with `.kickoff`. AutoGen has conversational agents with `.generate_reply`. An LLM provider has a client and a `messages.create`. A microservice has an HTTP route and a JSON body. None of these agree on a shape, so the moment you want a summarizer from one world to feed a classifier from another world, you are writing glue: unwrapping a response object here, reshaping a dict there, remembering which one is async and which one blocks, catching four different exception types, and hoping the whole thing runs in a sane order.

The frameworks themselves do not solve this, because each one wants to *be* your world. They are opinionated all the way down: adopt our agent model, our memory, our tool protocol, our orchestration. That is a reasonable bet for a framework, but it means two of them in one process fight rather than cooperate. What has been missing is a **neutral assembly line**: a thin, unopinionated layer whose only goal is to let heterogeneous workers cooperate, and to make the act of adding a new kind of worker cheap.

BYOA is that neutral layer. It deliberately owns very little. It does not want to be your agent framework. It wants to be the floor those frameworks stand on, the conveyor between them, and the inspector who checks the work as it passes. The value is not in any single adapter; it is in the fact that once something is adapted, it composes with everything else that has been adapted, and it does so under one execution model with one set of rules.

---

## 3. Why a factory metaphor, and why it is load-bearing

Metaphors in software are usually decoration. This one is structural, and it earns its keep by making the API predictable. When you accept "factory, line, station, part, product" as the vocabulary, a surprising number of design questions answer themselves.

A **factory** builds a line but does not run the work; it is the builder. A **line** is the built thing, validated and ready, that actually runs. A **station** is one place on the line where one worker does one job. A **part** is the thing travelling down the belt, and a **product** is what comes off the end. Because the metaphor is consistent, a newcomer can guess the shape of the API before reading the reference. They expect that you assemble a line before you run it (you do), that a station wraps a single worker (it does), that a part carries the work-in-progress plus some markings that accumulate as it moves (it does), and that the line can branch and rejoin like a real factory floor (it can). The metaphor is not a story told after the fact; it is the thing that keeps the API honest and teachable.

There is a second, quieter reason the factory framing matters. Factories care about **quality control**. A real assembly line has inspectors and gates: if a part fails inspection, it does not silently roll on to become a defective product. BYOA bakes that idea in as a first-class concept rather than an afterthought, and the metaphor is what makes it feel natural rather than bolted on.

---

## 4. The mental model you will teach from

Here is the smallest possible complete example, and it is worth reading slowly because every noun in it maps to a concept you will explain to others.

```python
from byoa import Factory

line = (
    Factory()
      .station("clean",   str.strip)
      .station("shout",   str.upper)
      .station("exclaim", lambda s: s + "!")
)
product = await line.run("  hello  ")   # product.output == "HELLO!"
```

Three things are happening. First, `Factory()` starts an empty line. Second, each `.station(name, worker)` call adds a station and, because no dependencies were named, chains it after the previous one: this is the "linear sugar." Third, `run` sends a **part** carrying `"  hello  "` down the belt; each station's worker transforms the payload and passes it on, and the value that falls off the end becomes the **product's** output.

Now the same machine, branching:

```python
f = Factory()
f.station("src",    lambda n: n)
f.station("double", lambda n: n * 2, after=["src"])
f.station("square", lambda n: n * n, after=["src"])
f.join("sum", after=["double", "square"], agent=lambda d: d["double"] + d["square"])
product = await f.run(3)   # 6 + 9 == 15
```

The moment you pass `after=[...]`, you have stopped drawing a straight line and started drawing a graph. `double` and `square` both depend on `src`, so they run in parallel. `sum` depends on both, so it waits for them and then receives their outputs joined into a dictionary keyed by station name. This is the same factory, the same vocabulary, just wired as a directed graph instead of a straight belt. The important teaching point is that **linear is not a different system from the DAG; it is a convenience over it.** You never graduate from one API to another. You just start naming dependencies when you need to.

The last concept in the mental model is the **quality gate**. Any station can carry a `check` that inspects the part after the worker runs and returns a verdict of pass, warn, or fail. A `gate` mode decides what a verdict does: advisory (record it, never block), block on fail, or block on warn-or-worse. This is the inspector on the line. It is optional, it is native to BYOA, and it is what lets the factory refuse to turn a defective part into a product.

---

## 5. The skeleton: three layers

Structurally, BYOA is three concentric layers, and keeping them separate is one of the most important decisions in the whole project.

The innermost layer is the **core engine**. It knows about parts, agents, stations, blueprints, the scheduler that runs them, and the native verdict types. It has no idea that HTTP exists, or that LangChain exists, or that there is a command line. It depends only on Pydantic for its data types. If you deleted every adapter and every interface, the core would still compile and run any worker that already speaks the `Agent` shape. This layer is the assembly line itself: belts, stations, and the logic that moves parts.

The middle layer is the **adapters**. This is the "bring your own" machinery: the code that takes something from the outside world and makes it stand at a station. Callables and HTTP live here in the light base install; MCP, LLM providers, and the big frameworks live here too but behind optional extras so they are only imported if you actually use them. The crown of this layer is `adapt()`, the function that looks at whatever you hand it and figures out which adapter applies. Adapters depend on the core, never the other way around.

The outermost layer is the **interfaces**: the ways a human or another program drives the factory. Today that is the command line (`byoa demo`, `byoa doctor`, `byoa inspect`) plus a key-free demonstration line. Planned for this layer are a REST service that serves a line over HTTP and an MCP server that exposes a line as a tool. Interfaces depend on the core and the adapters; nothing depends on interfaces.

```
   interfaces   (CLI, demo, doctor; planned: REST, MCP server)
        |
     adapters   (adapt(), callable, http/openapi, mcp, llm, frameworks, registry)
        |
   core engine  (Part/Product, Agent, Station, Blueprint, Scheduler, Verdict/Gate)
        |
     pydantic    (the only hard dependency of the core)
```

The reason this layering is worth guarding jealously is that it is what keeps the base install light and the core reusable. Dependencies flow strictly inward. A change to how HTTP works cannot ripple into the scheduler. A new interface cannot force a new core concept. And because the core has no knowledge of any specific agent technology, it will not age the way a framework-coupled core would when the framework of the month changes.

---

## 6. The core engine, part by part

### The Part and the Product

The thing that travels down the belt is a `Part`. It carries three things: a `payload` (the actual data, which can be anything), a `meta` dictionary (provenance and annotations that accumulate as the part moves), and an optional `content_type` hint. The reason a part is a small envelope rather than just the raw payload is that a factory needs to carry more than the material itself. It needs the paperwork: which station touched this, what the HTTP status was, which model produced this text. That paperwork lives in `meta`, and every time a worker produces output, BYOA stamps the station's name into it. When the run finishes, you get a `Product`: the final output, a boolean `ok`, an overall `verdict`, and a `trace` that is the full list of what happened at each station. The product is deliberately more than "the answer"; it is the answer plus the record of how it was made, which is exactly what you want when something goes wrong and you need to see where.

### The Agent protocol: the one shape everything becomes

At the very center of the design is a single, tiny contract:

```python
@runtime_checkable
class Agent(Protocol):
    name: str
    async def run(self, part: Part, ctx: Context) -> Part: ...
```

This is the narrow waist of the whole system. Everything a user brings is eventually turned into something with a `name` and an async `run` that takes a part and returns a part. The choice to make this a `Protocol` rather than a base class you must inherit from is deliberate and important: it means an object can *be* an agent without ever importing BYOA. Duck typing is the point. If your object already has a `name` and an async `run` with the right shape, BYOA will treat it as an agent and never wrap it. This keeps the coupling as loose as it can possibly be, and it is why the framework can claim to be neutral.

The choice to make `run` **async** is also deliberate. An assembly line's whole advantage is that independent stations can work at the same time. Async is the cheapest way to get that concurrency for the kind of work agents do, which is overwhelmingly I/O-bound: waiting on an HTTP response, waiting on an LLM, waiting on a subprocess. Synchronous workers are not shut out; the callable adapter runs blocking functions on a worker thread so they never freeze the event loop. But the native language of the line is async, because that is what lets a fan-out actually fan out.

### The Context

Alongside the part, every `run` receives a `Context`. It carries a `run_id`, a shared `state` dictionary that acts as a blackboard for the whole run, and an optional `deadline`. The deadline is expressed as a monotonic clock value so that the scheduler can compute, at any moment, how much time the run has left and refuse to start work that cannot finish in time. The context is how run-wide concerns travel without being threaded through every payload by hand.

### The Station

A `Station` is a small record: a name, the agent, an optional check, a gate mode, and an optional per-station timeout. It is intentionally dumb. It does not run anything itself; it is just the description of one spot on the line. Keeping the station as data rather than behavior is what lets the blueprint be inspected and reasoned about without executing anything.

### The Blueprint and why validation happens before running

When you call `Factory.compile()`, the nodes you have added become a `Blueprint`, and the blueprint is **validated before it is ever run**. Validation checks two things: that no station depends on a name that does not exist, and that the graph is acyclic. The cycle check uses Kahn's algorithm, repeatedly removing nodes with no remaining upstream dependencies; if any nodes are left over, they form a cycle and compilation fails with an error that names them. This "fail at build time, not at run time" stance is a small thing that pays off constantly. A typo in a dependency name, or an accidental loop, is caught the instant you compile, with a clear message, rather than manifesting as a hang or a confusing partial run later. The blueprint also knows how to describe itself as plain JSON (`topo_spec`), which is what powers `byoa inspect`. Note the honest limitation here: the *topology* serializes, but the live agents do not, because an arbitrary Python object or network client cannot be turned back into itself from JSON. So a blueprint's shape is portable and inspectable; rebuilding a runnable line from a saved spec is a future feature that will lean on the registry.

### The Scheduler: the actual machine

The scheduler is where the metaphor becomes real. It is a reactive loop rather than a fixed topological march, and the difference matters. On each pass it does three things. It marks any node whose barrier can never be satisfied as **skipped**. It launches every node whose barrier *is* satisfied. Then it waits for at least one running node to finish and absorbs the result. It repeats until nothing is running and nothing new can start.

"Reactive" means a node starts the moment its dependencies are ready, not when some global stage boundary is reached. Two independent branches of the graph run genuinely concurrently, and a slow branch never holds up a fast one that does not depend on it. Concurrency is bounded by a semaphore (default of eight) so that a very wide fan-out cannot spawn an unbounded number of simultaneous tasks; this is both a performance choice and a safety one. Every node run is wrapped so that a raised exception, a timeout, or a blocking gate all resolve to a recorded outcome rather than crashing the whole run. Timeouts are computed as the tighter of the station's own timeout and whatever remains of the run deadline, so neither can be exceeded.

The join semantics are worth stating precisely because people will ask. When a node has one contributing upstream, it receives that upstream's part directly, unwrapped, which is the ergonomic thing: a normal chain just passes values along. When a node has several contributing upstreams, their payloads are merged into a dictionary keyed by upstream station name, and their `meta` is merged too. This is why the `sum` station in the branching example received `{"double": 6, "square": 9}`, but a station with a single parent just receives the value.

### The Verdict, the Result, and the Gate

BYOA has its own three-value verdict: pass, warn, fail. It has a `Result` (a verdict plus a human reason), a `Check` (a function, sync or async, that looks at a part and returns a result), and a `GateMode` that decides what a verdict does to the flow. Off means the check runs for its signal but never blocks. Warn means only a fail blocks. Strict means a warn or a fail blocks. When a gate blocks, that node is marked failed, and its failure then propagates through the barrier logic downstream exactly as any other failure would.

The reason these verdict types are **native to BYOA and not borrowed** from anywhere is a decision covered in the tradeoffs section, but the short version is that it keeps the base install dependency-free and keeps the project honest about being a neutral layer. The overall product verdict is the worst verdict any station's check produced, unless the line failed to produce all its outputs, in which case it is fail.

---

## 7. How things plug in: the adapter story

This is the part people most want to understand, because it is the "bring your own" promise made concrete.

### `adapt()`: the on-the-fly connector maker

The centerpiece is a single function, `adapt(obj)`, whose job is to look at whatever you hand it and return an `Agent`. It tries possibilities in a deliberate order, and the order is the design:

First, if the object already satisfies the agent shape, it is returned untouched. Bring something that already speaks the protocol and BYOA gets out of the way entirely. Second, any custom or third-party adapters that have been registered get first crack, because the people extending the system should be able to override or specialize the built-in behavior. Third come the specific recognizers: an MCP reference, then framework agents (LangChain, CrewAI, AutoGen), then HTTP and OpenAPI endpoints. Last comes the universal fallback: if the object is merely callable, wrap it as a callable agent.

The ordering is not arbitrary. The most specific and least ambiguous cases are checked first, and the broadest catch-all (callable) is checked last, because almost everything in Python is callable in some sense and you do not want the fallback to shadow a more meaningful interpretation. A LangChain Runnable is technically callable, but you want it recognized as a LangChain agent, not naively invoked as a bare function, so its recognizer runs before the callable fallback.

### Recognizing frameworks without importing them

There is a subtle but important trick in how frameworks are detected. BYOA must not import LangChain just to check whether your object is a LangChain object, because that would drag a heavy dependency into everyone's process. So detection is done by inspecting the object's *type's module name* and the presence of tell-tale methods. If the type's module starts with `langchain` and the object has `.invoke`, it is treated as a LangChain agent. If the module starts with `crewai` and it has `.kickoff`, it is a Crew. This lets the recognizer answer "is this a LangChain thing?" without ever importing LangChain. The actual framework code is only touched when the adapter runs, and only if you brought such an object in the first place.

### The callable adapter and its "smart binding"

The most-used adapter is the humblest: wrap a plain function. Two decisions inside it are worth explaining. First, sync functions are run on a worker thread via `asyncio.to_thread`, so a blocking function on the line does not stall the event loop and starve the concurrent branches. Second, there is a small "binding" heuristic that decides how a part's payload becomes the function's arguments. If the function takes zero or one parameter, the payload is passed as a single argument. If the payload is a dictionary and the function's parameter names line up, it is spread as keyword arguments. If the payload is a list or tuple and the function takes several parameters, it is spread positionally. Otherwise it is passed as one value. This is what lets `str.upper`, a one-argument summarizer, and a two-argument `combine(first, second)` fed by a join all "just work" without you writing binding code. It is a heuristic, and heuristics have edges, but the rules are deterministic and documented so the behavior is predictable rather than magical.

### HTTP, OpenAPI, and reading a schema versus running code

The HTTP adapter posts a part's payload as JSON to an endpoint and returns the response. The OpenAPI path is more interesting: given a spec (a URL or a parsed document), it reads the schema to learn how to call the service and builds the request accordingly. The line that matters for trust is this: **the OpenAPI path only ever reads the schema; it never fetches or executes remote code.** Reading a description of an API is safe; running whatever an API hands back is not, and BYOA does not do the latter. There is also a basic SSRF guard that validates the URL scheme and, unless explicitly told otherwise, refuses to call internal, loopback, or link-local addresses. This guard is intentionally conservative and will be hardened further in the dedicated security pass, but even in its first form it closes the most obvious "make the server call its own metadata endpoint" class of attack.

### LLMs and MCP behind extras

LLM providers (Anthropic, OpenAI, Ollama) and MCP tools are real adapters, but their heavy client libraries are optional. They are imported lazily, at call time, and if the matching extra is not installed you get a clear "install byoa-sdk[cloud]" style error rather than an obscure import failure. API keys are only ever read from the environment or the user's config directory, never hard-coded and never written into a serialized blueprint. The LLM adapter defaults to the latest Claude model, and it is a plain prompt-in, text-out station: whatever comes down the belt is substituted into the prompt, and the model's text becomes the next part.

### The registry and entry points: extension without forking

Finally, the adapter layer is open. Anyone can teach `adapt()` a new trick in two ways. In-process, they call `register_adapter(name, matches, build)` with a predicate that recognizes their object and a builder that wraps it; later registrations take precedence, so extensions can specialize built-ins. Across packages, a third-party library declares an entry point in the `byoa.adapters` group, and BYOA discovers it automatically the first time `adapt()` runs. This is the same extension pattern used across the sibling projects in this ecosystem, and it means a new kind of worker can be supported by publishing a small package, with no change to BYOA itself. Extensibility without modification is the whole reason the registry exists.

---

## 8. The interfaces, and the demo that proves the machine

The command line is the first way to drive the factory. `byoa doctor` reports which optional adapter families are installed, so you can see at a glance whether, say, the MCP or cloud extras are present. `byoa inspect` prints a line's topology as JSON. And `byoa demo` is the one to show someone first, because it proves the entire thesis in a few seconds and needs no API key and no network.

The demo builds two versions of the same one-station line. The "broken" version has a summarizer with a bug: it returns an empty string. A quality check on the station requires non-empty output, so the gate blocks and the product comes back with a fail verdict and a recorded reason. The "fixed" version has a working summarizer, so the same line passes the gate and produces a real product. In one command you see the factory, the station, the worker, the quality gate refusing bad work, and then the same machine producing good work. That is the elevator pitch made executable. The REST service and the MCP server, which will let other programs and other agents drive a line remotely, are the next interfaces to be built, and they are exactly where the dedicated security work will concentrate because they are where untrusted input meets the machine.

---

## 9. The decisions and their tradeoffs

Every interesting system is a pile of tradeoffs, and being able to explain *why not the other thing* is what separates understanding from memorization. Here are the choices that shaped BYOA and what each one cost.

**Neutral layer, not a framework.** The biggest decision is what BYOA refuses to be. It is not trying to own your memory, your tool protocol, or your agent model. The benefit is that it composes with everything and ages slowly, because it has almost no surface that a changing ecosystem can break. The cost is that it does less for you out of the box than an all-in-one framework; it will not manage your conversation history or your vector store, because that is deliberately not its job. This is the right trade for a piece meant to sit *between* tools rather than replace them.

**Fully independent, with its own verdict types.** There was a real fork in the road here. An adjacent ecosystem defines a shared "report and verdict" contract, and BYOA could have depended on it so that its quality gates spoke that common language. The decision was to stay fully independent and define native `Verdict`, `Part`, and `Product` types instead. The benefit is a base install that depends on essentially nothing but Pydantic, and a project that is honestly standalone and adoptable by people who have never heard of that other ecosystem. The cost is that BYOA does not, today, emit that shared report format, so it cannot slot directly into that ecosystem's brain. The mitigation is planned: an optional bridge, behind an extra, that maps BYOA's native product onto that external contract for the people who want it. Independence in the core, interoperability as an opt-in: that is the shape of the compromise.

**A DAG core with a linear façade.** BYOA could have been a simple linear pipeline, which is what "assembly line" first suggests, and it would have been much less code. It could instead have exposed only a graph API, which is more powerful but heavier to learn. The choice was to build the graph engine underneath and offer the linear chain as sugar on top of it. The benefit is that beginners get the one-liner and never see the graph until they need it, while power users get fan-out, parallelism, and joins from the same object with no migration. The cost is a scheduler that is genuinely more complex than a `for` loop, with barrier logic and failure propagation to get right. That complexity is paid once, in one file, and everyone benefits.

**Barrier policies instead of "all or nothing."** When a station has several upstreams, the naive rule is "wait for all of them, and if any failed, give up." BYOA supports that (`all`), but also `k_of_n` (proceed when at least k upstreams succeed) and `optional` (proceed once everyone has settled, regardless of pass or fail). This is what lets a line be resilient: run three redundant extractors and continue as long as one succeeds, or attach a best-effort enrichment step whose failure should not sink the run. The cost is conceptual surface (three policies to explain instead of one) and a subtler definition of what "the line succeeded" even means, which leads directly to the next decision.

**"Succeeded" means the products were made, not that nothing ever failed.** Early on, the product was marked not-ok if any node anywhere failed. That turned out to be wrong in the presence of tolerant barriers: if a `k_of_n` join was explicitly told that one failing branch is fine, then that failure should not fail the whole run. So the rule was changed: the line is ok if every terminal node produced its output. A failure that a downstream barrier tolerated is recorded in the trace for honesty, but it does not, by itself, sink the product. This is a small semantic decision with a big effect on how resilient lines behave, and it is the kind of thing worth stating out loud because it is exactly what someone will question.

**Async as the native tongue, threads for the blockers.** Making `run` async buys real concurrency for I/O-bound work, which is what agents mostly do. The price is that the whole API is async and callers must be in an event loop, which is a small friction for simple scripts. Blocking functions are not excluded; they are shunted to threads. CPU-bound work that holds the GIL is the genuine weak spot of this model, and the honest answer is that such work belongs in a process or a service that a station then calls, not inside the event loop.

**A light base with heavy things behind extras.** The base install carries only what callables and HTTP need. Everything large (LLM clients, MCP, the frameworks, the web server) is an optional extra, imported lazily and only when used. The benefit is that `pip install byoa-sdk` is small and fast, and importing BYOA never drags in a dependency you did not ask for. The cost is a little ceremony (you must install the right extra, and the code must guard imports and raise friendly errors), plus the ongoing discipline of never letting a heavy import sneak into the core. It is a discipline worth keeping because it is the difference between a tool people reach for and one they hesitate to add.

**Duck-typed protocol over a mandatory base class.** Requiring everyone to subclass a BYOA base class would make detection trivial but coupling maximal. Using a runtime-checkable protocol means an object can satisfy the contract by accident of shape, without importing BYOA at all. The cost is that structural typing only checks that the methods exist, not that their signatures are perfect, so a malformed agent fails at call time rather than registration time. For a "bring anything" tool, that looseness is a feature, not a bug.

**Fail at compile, not at run.** Validating the graph when you compile it, rather than discovering problems mid-run, costs a little up-front work and the occasional "why won't this compile" moment. It buys clear, early, actionable errors instead of hangs and half-finished runs. For anything that orchestrates other systems, early failure with a good message is almost always the better trade.

---

## 10. What is deliberately not there yet

An honest architecture document says what is missing. Today BYOA has a solid, tested core, the adapter layer with `adapt()`, and the command-line interface with the demo. It does not yet have the REST service or the MCP server that would let other programs and agents drive a line remotely. It has a basic SSRF guard but has not yet been through its dedicated security pass, which is where request-size caps, connection and handler timeouts, constant-time authentication for the REST service, a fail-closed posture on any non-loopback bind, and several rounds of adversarial review will land. It is local-only by choice for now, so there is no published package, no public repository, and no hosted documentation. The optional bridge to the adjacent ecosystem's report contract is designed but not built. None of these gaps are accidental; they are the next phases, sequenced so that the machine is proven correct before it is exposed to the network and only then dressed up and shipped.

---

## 11. How to explain BYOA in sixty seconds

If someone stops you in a hallway: BYOA is a neutral assembly line for agents. You build a line with a factory, drop your existing agents onto stations, and run it to get a product. The agents can be anything, a function, a web endpoint, an MCP tool, a LangChain or CrewAI agent, an LLM, because a single function called `adapt()` looks at whatever you bring and wraps it in one uniform interface. Stations can run in a straight chain or as a branching graph with parallel steps that rejoin, and each station can carry a quality gate that stops bad work from becoming a finished product. The core is tiny and depends on almost nothing; the heavy integrations are optional add-ons that only load when used; and anyone can teach the system a new kind of agent by registering an adapter, without changing BYOA itself. It does not try to be your framework. It tries to be the floor your frameworks stand on and the belt between them.

---

## 12. Glossary

**Factory** — the builder you use to assemble a line; offers both the linear chaining sugar and the explicit dependency (DAG) API.
**Line** — a compiled, validated assembly line, ready to run parts.
**Station** — one node on the line: an agent plus an optional quality check and gate.
**Agent** — the uniform worker interface; anything with a `name` and an async `run(part, ctx) -> part`.
**adapt()** — the on-the-fly adapter creator that turns any brought object into an Agent.
**Part** — the envelope travelling down the belt: a payload plus accumulating metadata.
**Product** — what the line produces: the final output, an ok flag, an overall verdict, and a full trace.
**Barrier** — the fan-in policy for a node with several upstreams: all, k_of_n, or optional.
**Verdict / Result / Check / GateMode** — BYOA's native quality-control types: the judgement, the judgement-with-reason, the function that judges, and the rule for what a judgement does to the flow.
**Registry / entry points** — how new adapters are added, in-process or from another package, without modifying BYOA.

---

*This document is the narrative companion to the code. When it and the code disagree, the code wins, and this file should be corrected. — amitpatole*
