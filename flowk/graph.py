import types
import inspect
from typing import Callable, Any, Dict, List, Optional

from flowk.node import Node  # pyre-ignore
from flowk.utils import get_logger  # pyre-ignore

logger = get_logger(__name__)


class Graph:
    """
    Core graph orchestrator holding nodes, connections, and metadata.
    """

    def __init__(
        self,
        state_schema: Any = None,
        checkpoint_db: Optional[str] = None,
    ) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[str]] = {}
        self.routes: Dict[str, Dict[Any, str]] = {}
        self.entrypoint: Optional[str] = None
        self.state_schema = state_schema
        self.compiled: bool = False
        self.interrupt_before: List[str] = []
        self.checkpoint_db: Optional[str] = checkpoint_db

        from flowk.memory import MemoryStore  # pyre-ignore
        from flowk.storage import StorageRegistry
        MemoryStore.configure(checkpoint_db)
        StorageRegistry.configure(checkpoint_db)

    # ------------------------------------------------------------------
    # Node registration
    # ------------------------------------------------------------------

    def node(self, retries: int = 0, fallback: Optional[Callable] = None) -> Callable:
        """Decorator to register a function as a Graph node."""
        def decorator(func: Callable) -> Node:
            n = Node(func=func, retries=retries, fallback=fallback)
            self._register_node(n)
            return n  # Return the Node instance so callers can use it in connect()
        return decorator

    def _register_node(self, node: Node) -> None:
        """Registers a node instance."""
        self.nodes[node.name] = node
        if self.entrypoint is None:
            self.entrypoint = node.name
        if node.name not in self.edges:
            self.edges[node.name] = []

    # ------------------------------------------------------------------
    # Edge / routing API
    # ------------------------------------------------------------------

    def connect(self, from_node: Node, to_node: Node) -> None:
        """Creates a directional edge between from_node and to_node."""
        if from_node.name not in self.nodes:
            self._register_node(from_node)
        if to_node.name not in self.nodes:
            self._register_node(to_node)
        self.edges[from_node.name].append(to_node.name)

    def route(self, condition_fn: Callable, mapping_dict: Dict[Any, Node]) -> Node:
        """
        Creates a conditional branch point in the graph.
        At runtime the executor calls `condition_fn` and uses the return value
        as a key into `mapping_dict` to pick the next node.
        """
        router_node = Node(func=condition_fn, name=f"router_{condition_fn.__name__}")
        self._register_node(router_node)
        self.routes[router_node.name] = {
            result_key: target_node.name
            for result_key, target_node in mapping_dict.items()
        }
        return router_node

    def llm_router(
        self,
        targets: Dict[str, str],
        model: str = "gpt-4o-mini",
        fallback: Optional[str] = None,
    ) -> Callable:
        """
        Zero-boilerplate intelligent routing via LLM.
        Automatically uses an LLM to choose the next node based on descriptions.

        Args:
            targets: maps target node name -> description of when to use it.
                     e.g. {"search": "Use when user asks about current events"}
        """
        def decorator(func: Callable) -> Node:
            async def auto_router(state: dict) -> Optional[str]:
                user_context = func(state)
                if inspect.iscoroutine(user_context):
                    user_context = await user_context

                try:
                    import openai  # pyre-ignore
                    import json
                except ImportError:
                    raise ImportError(
                        "OpenAI is required for llm_router. Run `pip install flowk[openai]`"
                    )

                client = openai.AsyncOpenAI()

                system_prompt = (
                    "You are a routing supervisor for an autonomous agent. "
                    "Based on the USER CONTEXT, choose the MOST APPROPRIATE target node.\n"
                    "Available target nodes and their descriptions:\n"
                )
                for node_name, desc in targets.items():
                    system_prompt += f"- **{node_name}**: {desc}\n"

                system_prompt += (
                    "\nYou MUST strictly return a JSON object with a single key 'target' "
                    "containing the exact string of the chosen node name. Nothing else."
                )

                logger.info(f"🧠 LLM Router evaluating targets: {list(targets.keys())}")
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"USER CONTEXT:\n{str(user_context)}"},
                    ],
                    response_format={"type": "json_object"},
                )

                result = json.loads(response.choices[0].message.content)
                chosen = result.get("target")

                if chosen not in targets:
                    logger.warning(f"⚠️ LLM Router chose invalid target '{chosen}'. Using fallback.")
                    return fallback or list(targets.keys())[0]

                logger.info(f"🧭 LLM Router decision: routed to -> {chosen}")
                return chosen

            router_node = Node(func=auto_router, name=f"llm_router_{func.__name__}")
            self._register_node(router_node)
            self.routes[router_node.name] = {key: key for key in targets.keys()}
            if fallback and fallback not in self.routes[router_node.name]:
                self.routes[router_node.name][fallback] = fallback
            return router_node

        return decorator

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------

    def compile(self, interrupt_before: Optional[List[str]] = None) -> "Graph":
        """
        Freezes the graph structure and performs validation pre-checks.
        Provides Human-in-the-loop interrupt boundaries.
        """
        if not self.entrypoint:
            raise RuntimeError("Cannot compile: Graph has no entrypoint / nodes.")

        for source, edge_targets in self.edges.items():
            for target in edge_targets:
                if target not in self.nodes:
                    raise RuntimeError(
                        f"Edge compilation error: Target node '{target}' from '{source}' does not exist."
                    )
        
        # Persist topology for UI observability
        from flowk.storage import StorageRegistry
        nodes = [{"id": n.name, "name": n.name, "type": "agent" if "agent" in n.name.lower() else "node"} for n in self.nodes.values()]
        edges = []
        for src, targets in self.edges.items():
            for tgt in targets:
                edges.append({"source": src, "target": tgt, "type": "flow"})
        for src, mapping in self.routes.items():
            for val, tgt in mapping.items():
                edges.append({"source": src, "target": tgt, "type": "route", "label": str(val)})
        
        StorageRegistry.save_graph("default", {"nodes": nodes, "edges": edges})

        self.interrupt_before = interrupt_before if interrupt_before is not None else []  # pyre-ignore
        self.compiled = True
        return self

    def _ensure_compiled(self) -> None:
        if not self.compiled:
            self.compile()

    # ------------------------------------------------------------------
    # Execution API
    # ------------------------------------------------------------------

    def run(
        self,
        input_data: Any = None,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        initial_state: Optional[dict] = None,
    ) -> Any:
        """Runs the whole graph sequentially."""
        self._ensure_compiled()
        from flowk.executor import SequentialExecutor  # pyre-ignore
        executor = SequentialExecutor(self)
        return executor.execute(input_data, run_id=run_id, session_id=session_id, initial_state=initial_state)

    async def arun(
        self,
        input_data: Any = None,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        initial_state: Optional[dict] = None,
    ) -> Any:
        """Runs the graph asynchronously, enabling parallel branch execution."""
        self._ensure_compiled()
        from flowk.executor import AsyncExecutor  # pyre-ignore
        executor = AsyncExecutor(self)
        return await executor.execute(input_data, run_id=run_id, session_id=session_id, initial_state=initial_state)

    async def astream(
        self,
        input_data: Any = None,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        initial_state: Optional[dict] = None,
    ):
        """Yields execution events iteratively; executes parallel branches via asyncio.gather."""
        self._ensure_compiled()
        from flowk.executor import AsyncExecutor  # pyre-ignore
        executor = AsyncExecutor(self)
        async for event in executor.astream(input_data, run_id=run_id, session_id=session_id, initial_state=initial_state):
            yield event

    # ------------------------------------------------------------------
    # Developer utilities
    # ------------------------------------------------------------------

    def debug(self, input_data: Any = None, session_id: Optional[str] = None) -> Any:
        """Runs the whole graph with explicit debug printing."""
        from flowk.debugger import Debugger  # pyre-ignore
        d = Debugger(self)
        return d.run(input_data, session_id=session_id)

    def step(self) -> Any:
        """Returns an interactive stepping debugger object/generator."""
        from flowk.debugger import Debugger  # pyre-ignore
        return Debugger(self)

    def replay(self, run_id: str) -> Any:
        """Replays an execution trace."""
        from flowk.debugger import Debugger  # pyre-ignore
        d = Debugger(self)
        return d.replay(run_id)

    def test(self, input_data: Any, expected_output: Any) -> Any:
        """Convenience method to assert pipelining outcomes."""
        output = self.run(input_data)
        assert output == expected_output, f"Test failed. Expected {expected_output}, got {output}"
        print("✅ Graph Test passed.")
        return output

    def metrics(self) -> Any:
        """Returns metrics summary of executions."""
        from flowk.metrics import MetricsRegistry  # pyre-ignore
        return MetricsRegistry.get_summary()

    def show(self) -> None:
        """Visualize graph structure natively in terminal."""
        from flowk.visualization import show_graph  # pyre-ignore
        show_graph(self)

    # ------------------------------------------------------------------
    # Graph Composition
    # ------------------------------------------------------------------

    def as_node(self, state_key: Optional[str] = None) -> Node:
        """
        Wraps this entire graph into a single callable Node object.
        Allows for extremely clean Graph Composition (Sub-graphs).

        Args:
            state_key: If provided, the sub-graph will operate only on
                       state[state_key] instead of the entire parent state.
        """
        async def sub_graph_node(input_data: Any, state: dict) -> Any:
            sub_state = state.get(state_key, {}) if state_key else state
            result = await self.arun(input_data, initial_state=sub_state)
            if state_key:
                state[state_key] = sub_state
            return result

        sub_graph_node.__name__ = f"SubGraph_{id(self)}"
        return Node(func=sub_graph_node, name=sub_graph_node.__name__)

    # ------------------------------------------------------------------
    # 1-Click API Deployment
    # ------------------------------------------------------------------

    def serve(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """
        Instantly deploys the graph as a production-ready Web API (FastAPI).
        Provides /invoke and /stream endpoints automatically.
        """
        try:
            import uvicorn  # pyre-ignore
            from flowk.server import create_app  # pyre-ignore
        except ImportError:
            raise ImportError(
                "FastAPI and Uvicorn are required for serving the graph. "
                "Install them via: pip install 'flowk[api]'"
            )

        app = create_app(self)
        logger.info(f"🌐 Serving Flowk Graph on http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)
