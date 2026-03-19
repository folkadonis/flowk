# Flowk 🌊

[![PyPI version](https://img.shields.io/pypi/v/flowk.svg)](https://pypi.org/project/flowk/)
[![Python](https://img.shields.io/pypi/pyversions/flowk.svg)](https://pypi.org/project/flowk/)
[![CI](https://github.com/folkadonis/flowk/actions/workflows/python-package.yml/badge.svg)](https://github.com/folkadonis/flowk/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Flowk** is a lightweight, high-performance workflow orchestration engine specifically designed for AI and LLM pipelines. It offers a simpler, developer-first alternative to complex frameworks like LangGraph. 

Everything you need to build Enterprise Agentic Workflows is packed into pure, readable Python: async execution, dynamic routing, CLI visualizers, SQLite/Redis time-travel, Pydantic type-safety, API deployments, streaming, and a local Observability UI.

---

## 🚀 All Features

### Core Execution
- **Extremely Simple API:** Turn standard Python functions into executable graph nodes effortlessly.
- **Node Resiliency:** Configure Node retries, timeouts, and fallback policies automatically (`@g.node(retries=3)`).
- **Standard Routing:** Route branch paths explicitly using standard Python functions (`g.route()`).
- **🛡️ Type-Safety:** Graph states are strictly validated upon every transition using `Pydantic`.
- **⚡ Async & Streaming:** Natively await APIs and stream real-time events (`g.astream()`).
- **Parallel Fan-Out:** Split a node into three; Flowk natively runs them exactly concurrently via `asyncio.gather`.

### Intelligence
- **🧠 Zero-Boilerplate Auto-Routing:** Eliminate `if/else` logic by letting OpenAI/Anthropic pick your exact graph branches using strictly validated zero-shot classification (`@g.llm_router`).
- **📦 Multi-Agent Composition:** Build nested agent networks by packaging entire sub-graphs as natively executable Nodes (`g.as_node()`).

### Developer Experience & Tooling
- **🛑 Human-in-the-Loop:** Set breakpoints to pause execution and later resume the exact thread stacks.
- **🚀 1-Click API Deployment:** Turn any Flowk `.py` into a fully typed FastAPI instance in milliseconds (`g.serve()`).
- **Terminal Visualization:** Render beautiful CLI graphs of your execution layout (`g.show()`).
- **Time Travel Replays:** Encounter a bug? Flowk traces everything. Replay historical executions in debug mode (`g.replay()`).
- **📊 Observability Dashboard:** Track sessions and modify global Graph context visually through the local Streamlit dashboard (`flowk ui`).
- **🧩 Pluggable Metrics:** Hook models (e.g. OpenAIPlugin) into `MetricsRegistry` to precisely track token consumption and cost.

---

## 📦 Installation

Flowk is modular by design.

```bash
# Core execution engine
pip install flowk

# Add-ons:
pip install "flowk[api]"    # 1-Click FastAPI Deployment
pip install "flowk[ui]"     # Streamlit Observability Dashboard
pip install "flowk[llm]"    # Auto-Router & Token Metrics
pip install "flowk[redis]"  # Distributed Persistence

# Install Everything
pip install "flowk[all]"
```

---

## ⚡ Quick Start

Building your first AI agent pipeline with Flowk takes less than a minute.

```python
import asyncio
from pydantic import BaseModel
from flowk import Graph

# 1. Define strict state
class AgentState(BaseModel):
    query: str
    processed: bool = False

g = Graph(state_schema=AgentState)

# 2. Define Nodes
@g.node(retries=3)  # Built-in resiliency
async def intake(query: str, state: dict):
    state["query"] = query
    print(f"📥 Received: {query}")
    return query

@g.node()
async def agent(query: str, state: dict):
    state["processed"] = True
    print("🤖 Processing context...")
    return f"Processed Output for {query}"

# 3. Connect nodes
g.connect(intake, agent)

# 4. View Architecture
g.show()

# 5. Run async pipeline
if __name__ == "__main__":
    result = asyncio.run(g.arun("Calculate the speed of light."))
```

---

## 🧠 Zero-Boilerplate LLM Auto-Routing

Why write manual `if/else` logic when LLMs can intelligently route workflows based directly on your docstrings? Flowk handles the prompts and the deterministic structured outputs for you.

```python
@g.llm_router(
    model="gpt-4o-mini",
    targets={
        "math_node": "Use this if the query contains numbers or equations.",
        "search_node": "Use this if the user asks for real-time news."
    }
)
def supervisor_router(state: dict):
    return state.get("query", "")

g.connect(parse_input, supervisor_router) 
```

---

## 🚀 1-Click API Gen (FastAPI)

Skip writing API boilerplate. Flowk automatically converts your Graph and Pydantic models into a fully validated FastAPI instance with `/docs`, `/invoke`, and `/stream`.

```python
# Launch app
g = Graph(state_schema=MyState)
g.connect(A, B)

if __name__ == "__main__":
    g.serve(host="0.0.0.0", port=8000)
```

Invoke your pipeline instantaneously:
```bash
curl -X POST "http://localhost:8000/invoke" \
     -H "Content-Type: application/json" \
     -d '{"initial_state": {"user_id": 123}, "input_data": "Search for X"}'
```

---

## 🛑 Human-in-The-Loop (Interrupts)

Create breakpoints in your workflows. Execution suspends gracefully to allow human review (e.g. paying an invoice), letting you resurrect the session precisely where you left off.

```python
# Set visual breakpoint
g.compile(interrupt_before=["commit_payment_node"])

# Run pipeline until suspended
for event in g.astream(input_data, session_id="user_john"):
    if event["type"] == "interrupt":
        print("Payment halted. Waiting for human approval...")

# Resume from checkpoint using identical session_id
g.arun(None, session_id="user_john")
```

---

## 📊 Observability Dashboard & Persistence

Flowk effortlessly saves run-histories exactly as they mutate across node transactions.

```python
# Native Memory Configurations
g = Graph()                                         # Ephemeral RAM
g = Graph(checkpoint_db="local_traces.db")          # SQLite Storage
g = Graph(checkpoint_db="redis://localhost:6379/0") # Redis
```

Spin up the native **Streamlit Time-Machine Dashboard** to review these checkpoints visually without relying on generic SaaS providers:
```bash
flowk ui
```

---

## 📦 Multi-Agent Composition

Build powerful hierarchical orchestrations by compiling smaller sub-graphs and mounting them identically as nodes within a massive supervisor pipeline.

```python
# Internal Research Graph
research_graph = Graph()
research_graph.connect(search_web, summarize)

# Packaged perfectly as a Node
research_node = research_graph.as_node(state_key="research_metadata")

# Plugged into Chief Editor Agent
main_graph = Graph()
main_graph.connect(plan_outline, research_node)
```

---

## 🐞 Time Travel & Execution Telemetry

If a run fails in production, you can trace exactly what inputs hit what nodes.

```python
# Run your pipeline in debug mode
g.debug("input", session_id="user_1")

# Encountered a crash? Replay the precise global trajectory:
g.replay("run_id_outputted_by_telemetry")

# Track Cost Metrics via extensible Plugins
from flowk.plugins.llm import OpenAIPlugin
from flowk import MetricsRegistry

PluginManager.register(OpenAIPlugin(model="gpt-4o"))
print(MetricsRegistry.get_summary()) # => Evaluated 4040 tokens ($0.12)
```
