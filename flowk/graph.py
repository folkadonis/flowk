import types
from typing import Callable, Optional, Dict, List, Any

from flowk.node import Node

class Graph:
    """
    Core graph orchestrator holding nodes, connections, and metadata.
    """
    def __init__(self, state_schema=None):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[str]] = {}
        self.entrypoint: Optional[str] = None
        self.state_schema = state_schema
        self.compiled = False
        self.interrupt_before = []

    def node(self, retries: int = 0, fallback: Optional[Callable] = None):
        """Decorator to register a function as a Graph node."""
        def decorator(func: Callable):
            n = Node(func=func, retries=retries, fallback=fallback)
            self._register_node(n)
            return n  # Return the Node instance
        return decorator

    def _register_node(self, node: Node):
        """Registers a node instance."""
        self.nodes[node.name] = node
        if self.entrypoint is None:
            self.entrypoint = node.name
        if node.name not in self.edges:
            self.edges[node.name] = []

    def connect(self, from_node: Node, to_node: Node):
        """Creates a directional edge between from_node and to_node."""
        if from_node.name not in self.nodes:
            self._register_node(from_node)
        if to_node.name not in self.nodes:
            self._register_node(to_node)
            
        self.edges[from_node.name].append(to_node.name)

    def route(self, condition_fn: Callable, mapping_dict: Dict[Any, Node]):
        """
        Creates a conditional branch point in the graph runtime.
        Instead of a static edge, runtime inspects condition_fn.
        """
        # This will be constructed in a way the executor understands.
        # We can implement a special 'RouterNode' or append routing metadata to the graph.
        router_node = Node(func=condition_fn, name=f"router_{condition_fn.__name__}")
        self._register_node(router_node)
        
        # Attach routing metadata for the executor to understand.
        if not hasattr(self, "routes"):
            self.routes = {}
            
        self.routes[router_node.name] = {
            result_key: target_node.name 
            for result_key, target_node in mapping_dict.items()
        }
        
        return router_node

    def compile(self, interrupt_before: List[str] = None):
        """
        Freezes the graph structure and performs validation pre-checks.
        Provides Human-in-the-loop interrupt boundaries.
        """
        if not self.entrypoint:
            raise RuntimeError("Cannot compile: Graph has no entrypoint / nodes.")
            
        # Optional validation for dangling edges
        for source, targets in self.edges.items():
            for target in targets:
                if target not in self.nodes:
                    raise RuntimeError(f"Edge compilation error: Target node '{target}' from '{source}' does not exist.")
                    
        self.interrupt_before = interrupt_before or []
        self.compiled = True
        return self

    def _ensure_compiled(self):
        if not self.compiled:
            # Auto fallback compilation if User directly executes .run() without compiling
            self.compile()

    def run(self, input_data: Any = None, session_id: str = None):
        """Runs the whole graph sequentially."""
        self._ensure_compiled()
        from flowk.executor import SequentialExecutor
        executor = SequentialExecutor(self)
        return executor.execute(input_data, session_id=session_id)

    async def arun(self, input_data: Any = None, session_id: str = None):
        """Runs the graph asynchronously, enabling parallel branch execution."""
        self._ensure_compiled()
        from flowk.executor import AsyncExecutor
        executor = AsyncExecutor(self)
        return await executor.execute(input_data, session_id=session_id)

    async def astream(self, input_data: Any = None, session_id: str = None):
        """Yields execution events iteratively and executes parallel branches via asyncio.gather."""
        self._ensure_compiled()
        from flowk.executor import AsyncExecutor
        executor = AsyncExecutor(self)
        async for event in executor.astream(input_data, session_id=session_id):
            yield event

    def debug(self, input_data: Any = None, session_id: str = None):
        """Runs the whole graph with explicit debug printing."""
        from flowk.debugger import Debugger
        d = Debugger(self)
        return d.run(input_data, session_id=session_id)

    def step(self):
        """Returns an interactive stepping debugger object/generator."""
        from flowk.debugger import Debugger
        d = Debugger(self)
        return d

    def replay(self, run_id: str):
        """Replays an execution trace."""
        from flowk.debugger import Debugger
        d = Debugger(self)
        return d.replay(run_id)

    def test(self, input_data: Any, expected_output: Any):
        """Convenience method to assert pipelining outcomes."""
        output = self.run(input_data)
        assert output == expected_output, f"Test failed. Expected {expected_output}, got {output}"
        print("✅ Graph Test passed.")
        return output

    def metrics(self):
        """Returns metrics summary of executions."""
        from flowk.metrics import MetricsRegistry
        return MetricsRegistry.get_summary()

    def show(self):
        """Visualize graph structure natively in terminal."""
        from flowk.visualization import show_graph
        show_graph(self)
