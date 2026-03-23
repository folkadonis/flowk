import asyncio
import time
import uuid
from typing import Any, List, Optional, Tuple

from flowk.graph import Graph  # pyre-ignore
from flowk.state import GraphState  # pyre-ignore
from flowk.metrics import MetricsRegistry  # pyre-ignore
from flowk.storage import StorageRegistry  # pyre-ignore
from flowk.utils import get_logger  # pyre-ignore
from flowk.plugins.base import PluginManager  # pyre-ignore
from flowk.memory import MemoryStore  # pyre-ignore

logger = get_logger(__name__)


class SequentialExecutor:
    """Runs a graph synchronously and serially, executing nodes and chaining states."""

    def __init__(self, graph: "Graph") -> None:
        self.graph = graph

    def execute(
        self,
        input_data: Any = None,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        initial_state: Optional[dict] = None,
    ) -> Any:
        run_id = run_id or str(uuid.uuid4())

        if initial_state is not None:
            initial_data = initial_state
        else:
            initial_data = MemoryStore.get_state(session_id) if session_id else {}  # pyre-ignore

        state = GraphState(initial_data, schema=self.graph.state_schema)  # pyre-ignore

        try:
            state.validate()  # pyre-ignore
        except ValueError as e:
            logger.error(f"Initial state schema rejected: {e}")
            raise RuntimeError(f"Cannot start execution: {e}")

        current_node_name = self.graph.entrypoint  # pyre-ignore
        current_input = input_data

        if not current_node_name:
            logger.warning("Graph has no nodes to execute.")
            return current_input

        logger.info(f"Starting execution run: {run_id} (Session: {session_id or 'Anonymous'})")
        start_time = time.time()

        PluginManager.on_run_start(run_id, self.graph, current_input)  # pyre-ignore
        StorageRegistry.save_event(run_id, "run_start", None, {"input": current_input}, session_id=session_id)
        execution_trace: List[dict] = []

        while current_node_name:
            node = self.graph.nodes.get(current_node_name)  # pyre-ignore
            if not node:
                raise RuntimeError(f"Attempted to execute unregistered node '{current_node_name}'")

            node_start = time.time()
            logger.debug(f"Executing node: {current_node_name}")
            PluginManager.on_node_start(run_id, node, current_input, state)  # pyre-ignore
            StorageRegistry.save_event(run_id, "node_start", current_node_name, {"input": current_input, "state": state.to_dict()}, session_id=session_id)

            output: Any = None
            status: str = "success"
            error: Optional[str] = None

            try:
                output = node.execute(current_input, state)  # pyre-ignore
            except Exception as e:
                status = "error"
                error = str(e)
                logger.error(f"Node execution failed: {e}")

            node_duration = time.time() - node_start

            step_trace = {
                "step": len(execution_trace) + 1,
                "node": current_node_name,
                "input": current_input,
                "output": output,
                "state_snapshot": state.to_dict(),  # pyre-ignore
                "duration": node_duration,
                "status": status,
                "error": error,
            }
            execution_trace.append(step_trace)

            MetricsRegistry.record_node_execution(current_node_name, node_duration)  # pyre-ignore
            PluginManager.on_node_end(run_id, node, output, state)  # pyre-ignore
            StorageRegistry.save_event(run_id, "node_end", current_node_name, {"output": output, "state": state.to_dict(), "duration": node_duration, "status": status, "error": error}, session_id=session_id)

            if status == "error":
                StorageRegistry.save_trace(run_id, execution_trace, session_id=session_id)  # pyre-ignore
                StorageRegistry.save_event(run_id, "run_error", None, {"error": error}, session_id=session_id)
                if session_id:
                    MemoryStore.save_state(session_id, state.to_dict())  # pyre-ignore
                raise RuntimeError(f"Execution failed at node '{current_node_name}': {error}")

            current_input = output

            if current_node_name in self.graph.routes:  # pyre-ignore
                route_mapping = self.graph.routes[current_node_name]  # pyre-ignore
                next_node_name = route_mapping.get(output)
                if not next_node_name:
                    logger.debug(
                        f"Routing node '{current_node_name}' returned '{output}'. No route mapping matched. Ending."
                    )
                    break
                current_node_name = next_node_name
            else:
                edges = self.graph.edges.get(current_node_name, [])  # pyre-ignore
                if not edges:
                    break
                current_node_name = edges[0]
                if len(edges) > 1:
                    logger.warning(
                        f"Multiple edges from '{node.name}', but running sequentially. Selected '{current_node_name}'."  # pyre-ignore
                    )

        total_duration = time.time() - start_time
        StorageRegistry.save_trace(run_id, execution_trace, session_id=session_id)  # pyre-ignore
        StorageRegistry.save_event(run_id, "run_end", None, {"output": current_input, "duration": total_duration}, session_id=session_id)
        MetricsRegistry.record_run(total_duration)  # pyre-ignore
        PluginManager.on_run_end(run_id, self.graph, current_input)  # pyre-ignore

        if session_id:
            MemoryStore.save_state(session_id, state.to_dict())  # pyre-ignore

        logger.info(f"Execution run completed in {total_duration:.3f}s")
        return current_input


class AsyncExecutor:
    """Runs a graph asynchronously, supporting parallel node execution fan-out and real-time streaming."""

    def __init__(self, graph: "Graph") -> None:
        self.graph = graph

    async def execute(
        self,
        input_data: Any = None,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        initial_state: Optional[dict] = None,
    ) -> Any:
        """Helper to run the stream until finish and return the final output."""
        last_output = input_data
        async for event in self.astream(input_data, run_id, session_id, initial_state):
            if event["type"] == "node_end":
                last_output = event["output"]
            elif event["type"] == "interrupt":
                logger.warning(f"Execution interrupted at node(s): {event['nodes']}")
                return last_output
        return last_output

    async def astream(
        self,
        input_data: Any = None,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None,
        initial_state: Optional[dict] = None,
    ):
        """Yields execution events iteratively and executes parallel branches via asyncio.gather."""
        run_id = run_id or str(uuid.uuid4())

        if initial_state is not None:
            initial_data: dict = initial_state
        else:
            initial_data = MemoryStore.get_state(session_id) if session_id else {}  # pyre-ignore

        state = GraphState(initial_data, schema=self.graph.state_schema)  # pyre-ignore

        try:
            state.validate()  # pyre-ignore
        except ValueError as e:
            logger.error(f"Initial state schema rejected: {e}")
            raise RuntimeError(f"Cannot start execution: {e}")

        active_nodes: List[Tuple[str, Any]] = (
            [(self.graph.entrypoint, input_data)] if self.graph.entrypoint else []  # pyre-ignore
        )
        execution_trace: List[dict] = []

        logger.info(f"Starting async execution run: {run_id} (Session: {session_id or 'Anonymous'})")
        start_time = time.time()
        PluginManager.on_run_start(run_id, self.graph, input_data)  # pyre-ignore
        StorageRegistry.save_event(run_id, "run_start", None, {"input": input_data}, session_id=session_id)

        while active_nodes:
            executable: List[Tuple[str, Any]] = []
            interrupted: List[str] = []

            for node_name, node_input in active_nodes:
                if node_name in self.graph.interrupt_before:  # pyre-ignore
                    interrupted.append(node_name)
                else:
                    executable.append((node_name, node_input))

            if not executable:
                if interrupted:
                    if session_id:
                        MemoryStore.save_state(session_id, state.to_dict())  # pyre-ignore
                    StorageRegistry.save_event(run_id, "run_interrupt", None, {"nodes": interrupted}, session_id=session_id)
                    yield {"type": "interrupt", "nodes": interrupted, "state": state.to_dict()}  # pyre-ignore
                break

            tasks = [
                self._arun_node(name, inp, state, run_id, execution_trace, session_id=session_id)  # pyre-ignore
                for name, inp in executable
            ]
            results = await asyncio.gather(*tasks)

            for res in results:
                yield {"type": "node_end", "node": res["node"], "output": res["output"], "state": state.to_dict()}  # pyre-ignore

            next_layer: List[Tuple[str, Any]] = []
            for res in results:
                node_name = res["node"]
                output = res["output"]
                status = res["status"]

                if status == "error":
                    if session_id:
                        MemoryStore.save_state(session_id, state.to_dict())  # pyre-ignore
                    StorageRegistry.save_event(run_id, "run_error", node_name, {"error": res.get("error")}, session_id=session_id)
                    raise RuntimeError(
                        f"Async execution failed at node '{node_name}': {res.get('error')}"
                    )

                if node_name in self.graph.routes:  # pyre-ignore
                    route_mapping = self.graph.routes[node_name]  # pyre-ignore
                    next_node = route_mapping.get(output)
                    if next_node:
                        next_layer.append((next_node, output))
                    else:
                        logger.debug(f"Routing node '{node_name}' returned '{output}'. No route found.")
                else:
                    edges = self.graph.edges.get(node_name, [])  # pyre-ignore
                    for edge in edges:
                        next_layer.append((edge, output))

            active_nodes = next_layer

        total_duration = time.time() - start_time
        StorageRegistry.save_trace(run_id, execution_trace, session_id=session_id)  # pyre-ignore
        StorageRegistry.save_event(run_id, "run_end", None, {"duration": total_duration}, session_id=session_id)
        MetricsRegistry.record_run(total_duration)  # pyre-ignore
        PluginManager.on_run_end(run_id, self.graph, None)  # pyre-ignore

        if session_id:
            MemoryStore.save_state(session_id, state.to_dict())  # pyre-ignore

        logger.info(f"Async execution run completed in {total_duration:.3f}s")

    async def _arun_node(
        self,
        node_name: str,
        current_input: Any,
        state: "GraphState",
        run_id: str,
        execution_trace: List[dict],
        session_id: Optional[str] = None,
    ) -> dict:
        node = self.graph.nodes.get(node_name)  # pyre-ignore
        if not node:
            raise RuntimeError(f"Unregistered node '{node_name}'")

        node_start = time.time()
        logger.debug(f"Async executing node: {node_name}")
        PluginManager.on_node_start(run_id, node, current_input, state)  # pyre-ignore
        StorageRegistry.save_event(run_id, "node_start", node_name, {"input": current_input, "state": state.to_dict()}, session_id=session_id)

        output: Any = None
        status: str = "success"
        error: Optional[str] = None

        try:
            output = await node.aexecute(current_input, state)  # pyre-ignore
        except Exception as e:
            status = "error"
            error = str(e)
            logger.error(f"Node async execution failed: {e}")

        node_duration = time.time() - node_start

        step_trace = {
            "step": len(execution_trace) + 1,
            "node": node_name,
            "input": current_input,
            "output": output,
            "state_snapshot": state.to_dict(),  # pyre-ignore
            "duration": node_duration,
            "status": status,
            "error": error,
        }
        execution_trace.append(step_trace)

        MetricsRegistry.record_node_execution(node_name, node_duration)  # pyre-ignore
        PluginManager.on_node_end(run_id, node, output, state)  # pyre-ignore
        StorageRegistry.save_event(run_id, "node_end", node_name, {"output": output, "state": state.to_dict(), "duration": node_duration, "status": status, "error": error}, session_id=session_id)

        return {"node": node_name, "output": output, "status": status, "error": error}
