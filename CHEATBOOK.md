# Flowk 🌊 Cheatbook

A comprehensive quick-reference guide for building, orchestrating, and observing AI agent workflows with Flowk.

---

## 1. Core Classes & Decorators

### `Graph`
The central coordinator for building and executing workflows.

| Method | Description | Example |
| :--- | :--- | :--- |
| `Graph(state_schema=None, checkpoint_db=None)` | Initialize a graph. Optionally provide a Pydantic schema and a connection string for persistence. | `g = Graph(state_schema=MyState, checkpoint_db="flow.db")` |
| `@g.node(retries=0, fallback=None)` | Decorator to register a function as a node. | `@g.node(retries=3)\ndef task(data): return data` |
| `g.connect(from_node, to_node)` | Connect two nodes sequentially. | `g.connect(start_node, end_node)` |
| `g.route(condition_fn, mapping_dict)` | Create a deterministic branch point. | `g.route(decider, {"yes": node_a, "no": node_b})` |
| `@g.llm_router(targets, model="gpt-4o-mini")` | Decorator for intelligent LLM-based auto-routing. | `@g.llm_router(targets={"a": "desc", "b": "desc"})\ndef router(state): return state["text"]` |
| `g.compile(interrupt_before=None)` | Freeze graph and set breakpoints. | `g.compile(interrupt_before=["final_step"])` |
| `g.run(input, session_id=None)` | Execute graph synchronously. | `result = g.run("Hello")` |
| `await g.arun(input, session_id=None)` | Execute graph asynchronously (supports parallel branches). | `res = await g.arun("Query")` |
| `async for event in g.astream(input)` | Stream execution events (JSON objects). | `async for e in g.astream(inp): print(e)` |
| `g.as_node(state_key=None)` | Wrap an entire graph into a single node for composition. | `sub_node = sub_graph.as_node(state_key="sub")` |
| `g.serve(host="0.0.0.0", port=8000)` | 1-Click FastAPI deployment. | `g.serve(port=8080)` |
| `g.show()` | Visualize graph in terminal as ASCII. | `g.show()` |
| `g.debug(input)` | Run with verbose terminal logging. | `g.debug("test")` |
| `g.replay(run_id)` | Replay a historical execution trace. | `g.replay("run-123")` |

---

## 2. Advanced Features

### Persistence: `StorageRegistry` & `MemoryStore`
Handled automatically when `Graph()` evaluates its environment. Defaults implicitly to `.flowk/flowk.db`.

- **Default SQLite**: `.flowk/flowk.db`
- **Custom SQLite**: `checkpoint_db="flow.db"`
- **Redis**: `checkpoint_db="redis://localhost:6379/0"`

| Method | Description |
| :--- | :--- |
| `StorageRegistry.get_trace(run_id)` | Retrieve raw execution trace. |
| `StorageRegistry.list_runs(session_id=None)` | List historical run IDs. |
| `StorageRegistry.get_events(run_id)` | Get the full immutable event sourcing log. |

### Metrics: `MetricsRegistry` & `PluginManager`
Track token usage and execution performance.

| Method | Description | Example |
| :--- | :--- | :--- |
| `MetricsRegistry.get_summary()` | Returns JSON of token usage, costs, and node times. | `print(g.metrics())` |
| `PluginManager.register(plugin)` | Register an LLM metrics plugin (OpenAI/Anthropic). | `PluginManager.register(OpenAIPlugin())` |

---

## 3. CLI Commands

| Command | Description |
| :--- | :--- |
| `flowk dev` | Launch the **Developer Environment** (API + Dashboard + Browser). |
| `flowk ui` | Launch just the observation dashboard on port 8502. |
| `flowk runs list` | List all available runs saved in the `.flowk/` store. |
| `flowk runs inspect <id>` | Print the absolute event log timeline for a specified run. |
| `flowk serve <file>:<graph>` | Serve a graph file as a FastAPI app. |

---

## 4. Examples

### A. Minimal Async Graph
```python
from flowk import Graph

g = Graph()

@g.node()
async def greet(name: str):
    return f"Hello {name}!"

@g.node()
async def process(msg: str):
    return msg.upper()

g.connect(greet, process)

# Run it
if __name__ == "__main__":
    import asyncio
    res = asyncio.run(g.arun("World"))
    print(res) # => "HELLO WORLD!"
```

### B. Intelligent Router
```python
@g.llm_router(targets={
    "billing": "Queries about invoices or payments",
    "support": "General help or technical issues"
})
def supervisor(state):
    return state["user_message"]

g.connect(input_node, supervisor)
```

### C. Human-in-the-Loop
```python
g.compile(interrupt_before=["payment"])

# Running this will stop before 'payment'
async for event in g.astream(data, session_id="abc"):
    if event["type"] == "interrupt":
        print("PAUSED. Waiting for review.")

# Resume later with same session_id
await g.arun(None, session_id="abc")
```
