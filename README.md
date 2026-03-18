# Flowk 🌊



[![PyPI version](https://img.shields.io/pypi/v/flowk.svg)](https://pypi.org/project/flowk/)
[![Python](https://img.shields.io/pypi/pyversions/flowk.svg)](https://pypi.org/project/flowk/)
[![CI](https://github.com/folkadonis/flowk/actions/workflows/python-package.yml/badge.svg)](https://github.com/folkadonis/flowk/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Flowk** is a lightweight, high-performance workflow orchestration engine specifically designed for AI and LLM pipelines. It offers a simpler, developer-first alternative to complex frameworks like LangGraph, with native support for async execution, parallel DAGs, Pydantic state validation, conditional routing, human-in-the-loop interrupts, session memory, SQLite checkpointing, and real-time streaming — all in pure Python.

---

## 🚀 Key Features
- **Extremely Simple API:** Turn standard Python functions into executable graph nodes seamlessly.
- **Node Retries & Fallbacks:** Built-in resilience out-of-the-box.
- **Dynamic Routing:** Direct your execution paths dynamically on the fly based on outputs.
- **Stepping & Time Travel:** Pausable execution steps and total trace replay capabilities.
- **Telemetry & Visualization:** Live terminal tracking, cost metric emulation, and highly readable CLI flow rendering.
- **Pluggable Architecture:** Tap into lifecycle hooks using Plugins effortlessly.

---

## 📦 Installation

Install Flowk directly from PyPI:
```bash
pip install flowk
```

Or install the latest development version from GitHub:
```bash
pip install git+https://github.com/folkadonis/flowk.git
```

### Requirements
- Python ≥ 3.8
- `pydantic ≥ 2.0.0` (installed automatically)

---

## 🛠️ Core Concepts

### 1. The Graph
The `Graph` is the brain of Flowk. It wires up nodes sequentially or through condition-based router intersections:
```python
from flowk import Graph
g = Graph()
```

### 2. Nodes & State
Nodes are just typical Python functions decorated with `@g.node()`. An internal `GraphState` mutable dictionary is implicitly available across your pipeline.

```python
# Pass `state` as an argument to read/write shared data across the lifecycle map
@g.node(retries=3)
def prepare_prompt(input_text: str, state: dict):
    state["original_query"] = input_text
    return input_text.upper()
```

### 3. Connections
Bind nodes synchronously. The `Graph` auto-detects the first configured node as the entrypoint. All data returned from Node A automatically gets piped into Node B as the `input_text`.

```python
g.connect(prepare_prompt, call_llm)
```

### 4. Routing (Conditional Branching)
When execution forks depend on context (e.g., standard request vs. priority request), use `g.route()`.
```python
def check_priority(result_from_previous_node: str):
    return "fast" if "URGENT" in result_from_previous_node else "standard"

# Map condition strings to actual handling Nodes
router_node = g.route(check_priority, {
    "fast": priority_handler_node,
    "standard": normal_handler_node
})

g.connect(prepare_prompt, router_node)
```

---

## 🔍 Tooling & Observability

Flowk ships with beautiful tooling crafted identically for both fast prototyping and robust production monitoring. 

### Visualizing Graphs
Check exactly how your configuration looks using `g.show()`.
```text
==================================================
📊 FLOWK EXECUTION FLOW
==================================================

[ prepare_prompt ]
  │
  ▼
⟪ priority_check ⟫ (Router)
  │
  ├─[fast]──────► [ priority_handler ]
  │                 │
  │                 ▼
  │               [ cleanup ]
  │
  └─[standard]──► [ standard_handler ]
                    │
                    ▼
                  [ cleanup ] 🔄 (already visited)

==================================================
```

### Metrics Tracking
Built-in timing tracking per node alongside mock LLM tracking usage:
```python
g.run("Hello!")

from flowk import MetricsRegistry
print(MetricsRegistry.get_summary())
```

### 🧠 Session Memory Management
Flowk supports native execution memory persistence across multiple `.run()` calls via the `session_id` parameter. This is critically useful for multi-turn chat workflows where the LLM needs to continually append messages to the `GraphState` instead of wiping the slate clean!

```python
# Turns persist data appended into state automatically
r1 = g.run("Hello", session_id="user_john")
r2 = g.run("Are you there?", session_id="user_john")

r3_anon = g.run("Who am I?") # Anonymous runs use empty states
```

### ⚡ Async, Streaming, and Parallel Execution (v2)
Flowk utilizes high-performance asynchronous primitives to match enterprise scale:
- Define any node as `async def` and Flowk natively awaits it without blocking the thread pool.
- Use `g.arun()` for standard async resolution.
- Broadcast real-time node outputs manually using `async for event in g.astream(...)`. This is extremely optimal for mapping LLM outputs into WebSocket frontends!
- **Fan-Out Parallelism:** If a node splits into multiple separate nodes, Flowk executes all concurrent branches exactly concurrently using `asyncio.gather`. 

### 🛑 Human-in-The-Loop (Breakpoints)
Need a human to review an action before it commits to a database? Interrupt the graph!
```python
# 1. Compile the graph with a breakpoint
g.compile(interrupt_before=["commit_to_database"])

# 2. Execution will stop and exit when reaching the node
for event in g.astream(input_data, session_id="user_1"):
    if event["type"] == "interrupt":
        print("Waiting for human...")
        
# 3. Later, resume using the exact same session_id!
g.arun(None, session_id="user_1")
```

### 🛡️ Pydantic Safe-State Validation
Never let a silent property typo crash a 20-minute LLM pipeline again. Wrap your shared state in a Pydantic schema:
```python
from pydantic import BaseModel
class AgentState(BaseModel):
    messages: list
    cost: float

g = Graph(state_schema=AgentState)
# Flowk will validate `AgentState(**state)` between EVERY node execution.
```

### Debug & Time Travel
Encountering bugs in a complex run? Flowk saves runs by default!
- To run with highly verbose sequential logging, replace `g.run()` with `g.debug()`.
- To sequentially replay historic traces visually in terminal, grab the `run_id` outputted from any run:  
  `g.replay("run-123-abc")`

### 📦 Graph Composition (Sub-Graphs)
Flowk allows you to nest entire graphs into other graphs, enabling you to build complex multi-agent systems where each "Node" is itself a full workflow.
```python
research_subgraph = Graph()
# ... build your research workflow ...

main_graph = Graph()
# Use it as a node with isolated state scoping!
research_node = research_subgraph.as_node(state_key="research_data")
main_graph.connect(input_node, research_node)
```

### 🗄️ Scalable Redis Persistence
For enterprise applications requiring distributed state, Flowk now supports Redis natively as a checkpointing backend.
```python
g = Graph(checkpoint_db="redis://localhost:6379/0")
```

---

## 🧩 Plugins (Extensions)
Flowk includes native plugins for popular LLM providers that capture token usage and costs automatically:
- `OpenAIPlugin`
- `AnthropicPlugin`

```python
from flowk.plugins.llm import OpenAIPlugin
PluginManager.register(OpenAIPlugin(model="gpt-4o"))
```

---

## 📦 Installation
Install core:
```bash
pip install flowk
```

Install with optional enterprise features:
```bash
pip install "flowk[openai,redis]"
```

---

## 🛠️ Core Concepts
