# 🧠 Flowk Platform Architecture

Flowk is a hybrid workflow orchestration system designed for production-grade AI and LLM pipelines. It prioritizes deterministic execution, immutable observability (event sourcing), and a zero-config developer experience.

---

## 1. Architecture Overview

Flowk operates on a layered architecture, allowing it to scale from a local ephemeral script to a distributed, multi-worker FastAPI microservice.

```mermaid
graph TD
    subgraph Client Layer
        UI[React Dashboard v2]
        CLI[Flowk CLI]
        SDK[Python SDK]
    end

    subgraph API Gateway Layer
        FastAPI[FastAPI Server]
        Routes[invoke / async / stream]
    end

    subgraph Orchestration Engine
        Graph[Graph DAG Coordinator]
        Executor[Sequential / Async Executors]
        StateManager[Pydantic State Validator]
    end
    
    subgraph Event & Persistence Layer
        Storage[StorageRegistry]
        Events[Event Sourcing Logs]
        Traces[State Snapshots]
    end

    subgraph Data Stores
        SQLite[(SQLite default)]
        Redis[(Redis distributed)]
    end

    Client Layer -->|HTTP/REST| API Gateway Layer
    API Gateway Layer --> Orchestration Engine
    Orchestration Engine --> Event & Persistence Layer
    Event & Persistence Layer --> SQLite
    Event & Persistence Layer --> Redis
```

### Core Design Principles
1. **Deterministic first, AI second:** Workflows are standard code. LLMs are just specialized nodes within that code.
2. **Explicit State:** State is globally typed (Pydantic), mutated carefully, and snapshotted at every step.
3. **Observability Native:** Event sourcing guarantees a perfect audit trail. You can time-travel and replay any execution.

---

## 2. Component Breakdown

### A. Graph Orchestration Engine (`graph.py`, `node.py`, `executor.py`)
- **Nodes**: Wrapped Python functions (`@g.node()`) carrying retry, timeout, and fallback policies.
- **Edges**: Deterministic sequential constraints (`g.connect(A, B)`). Parallel fan-out is handled natively when multiple edges diverge from a single node.
- **Interrupts**: `g.compile(interrupt_before=[...])` suspends the execution loop, yielding control for Human-in-the-loop workflows.

### B. State Management System (`state.py`)
- The context passed between nodes is governed by a strict `Pydantic` schema (`state_schema`).
- Invalid mutations raise hard errors before the next node executes, preventing cascading AI hallucination failures.
- The `StateSnapshot` is recorded sequentially.

### C. Event Sourcing Layer (`storage.py`)
Every Node transition emits a discrete event identifying:
- `run_id`, `session_id`, `node`, `type` (e.g., `node_start`, `node_end`, `run_error`), `timestamp`, and the `data` (payload/snapshot).
- Stored gracefully in `.flowk/flowk.db` (SQLite) or a remote Redis cluster.

### D. API Layer (`server.py`)
Translates the `Graph` into a full-fledged FastAPI application via `g.serve()`.
- **Sync**: `POST /invoke`
- **Async Background**: `POST /async` & `GET /status/{run_id}`
- **Streaming**: `POST /stream` (Server-Sent Events)

### E. Observability Dashboard (`ui/v2/`)
A React-based SPA that attaches to the API layer, providing:
- SVG Graph topological visualization.
- Interactive Session & Run history sidebar.
- Trace step-throughs & Event Log timelines.
- State Diffing algorithms highlighting exactly what keys mutated over time.

---

## 3. Core Implementation Showcase

**1. The Graph & State**
```python
from pydantic import BaseModel
from flowk import Graph

class AgentState(BaseModel):
    query: str
    result: str = ""
    retry_count: int = 0

g = Graph(state_schema=AgentState)
```

**2. Resilient Nodes**
```python
@g.node(retries=3, timeout=10.0)
async def fetch_data(query: str, state: dict):
    state["query"] = query
    # Operations...
```

**3. Hybrid Agent Node (LLM)**
```python
@g.llm_router(
    model="gpt-4o",
    targets={"search_tool": "Use this to search the web", "calculator": "Math operations"}
)
def intelligent_router(state: dict):
    return state["query"]
```

**4. Event Sourcing & Storage Standard**
By default, running `g.arun("...")` utilizes the injected `StorageRegistry`:
```python
# Behind the scenes in executor.py
StorageRegistry.save_event(
    run_id=self.run_id,
    event_type="node_end",
    node=node.name,
    data={"state_snapshot": current_state.copy()}
)
```

---

## 4. Example Usage

**1. Local Development (CLI)**
```bash
# Start API on :8502, launch React dashboard, and open browser automatically
flowk dev

# Review historical executions in standard output
flowk runs list
flowk runs inspect <run_id>
```

**2. Time-Travel Debugging (Python SDK)**
```python
# A run failed in production. Grab the run_id from terminal or via REST:
run_id = "run-a1b2c3d4"

# Replay identical execution trajectories, stepping through the exact historic state
g.replay(run_id)
```

---

## 5. Future Improvements (Phase 2 & 3 Roadmap)

While Flowk v1 core is stable, scaling to distributed production entails:

1. **Distributed Celery/Redis Execution Layer:**
   When `POST /async` is called, jobs should push horizontally into a Redis Message Queue (RQ or Celery), where decentralized worker nodes process the graphs asynchronously.
   
2. **Pluggable Cost Engine:**
   Implementing a global `MetricsRegistry` middleware. Example:
   ```python
   @flowk.plugin("llm_cost")
   def track_openai_tokens(event): ...
   ```
   
3. **Advanced State Diff Algorithms:**
   Implementing deep-nested JSON diffing (e.g., DeepDiff) directly into the UI.

4. **Multi-User Tenant System:**
   Isolating session architectures by API key and namespace within `flowk.db`.
