import time
import uuid
from typing import Any

from flowk.graph import Graph
from flowk.state import GraphState
from flowk.metrics import MetricsRegistry
from flowk.storage import StorageRegistry
from flowk.utils import logger
from flowk.plugins.base import PluginManager
from flowk.memory import MemoryStore

class SequentialExecutor:
    """Runs a graph synchronously and serially, executing nodes and chaining states."""
    
    def __init__(self, graph: Graph):
        self.graph = graph

    def execute(self, input_data: Any = None, run_id: str = None, session_id: str = None) -> Any:
        run_id = run_id or str(uuid.uuid4())
        
        # Restore session memory if requested
        initial_data = MemoryStore.get_state(session_id) if session_id else {}
        state = GraphState(initial_data, schema=self.graph.state_schema)
        
        # Auto-validate the starting context
        try:
            state.validate()
        except ValueError as e:
            logger.error(f"Initial state schema rejected: {e}")
            raise RuntimeError(f"Cannot start execution: {e}")
            
        current_node_name = self.graph.entrypoint
        current_input = input_data

        if not current_node_name:
            logger.warning("Graph has no nodes to execute.")
            return current_input

        logger.info(f"Starting execution run: {run_id} (Session: {session_id or 'Anonymous'})")
        start_time = time.time()
        
        PluginManager.on_run_start(run_id, self.graph, current_input)
        execution_trace = []

        while current_node_name:
            node = self.graph.nodes.get(current_node_name)
            if not node:
                raise RuntimeError(f"Attempted to execute unregistered node '{current_node_name}'")
                
            node_start = time.time()
            logger.debug(f"Executing node: {current_node_name}")
            PluginManager.on_node_start(run_id, node, current_input, state)

            try:
                output = node.execute(current_input, state)
                status = "success"
                error = None
            except Exception as e:
                output = None
                status = "error"
                error = str(e)
                logger.error(f"Node execution failed: {e}")
            
            node_duration = time.time() - node_start
            
            step_trace = {
                "step": len(execution_trace) + 1,
                "node": current_node_name,
                "input": current_input,
                "output": output,
                "state_snapshot": state.to_dict(),
                "duration": node_duration,
                "status": status,
                "error": error
            }
            execution_trace.append(step_trace)
            
            MetricsRegistry.record_node_execution(current_node_name, node_duration)
            PluginManager.on_node_end(run_id, node, output, state)

            if status == "error":
                StorageRegistry.save_trace(run_id, execution_trace)
                if session_id:
                    MemoryStore.save_state(session_id, state.to_dict())
                raise RuntimeError(f"Execution failed at node '{current_node_name}': {error}")

            current_input = output
            
            if hasattr(self.graph, "routes") and current_node_name in self.graph.routes:
                route_mapping = self.graph.routes[current_node_name]
                next_node_name = route_mapping.get(output)
                
                if not next_node_name:
                    logger.debug(f"Routing node '{current_node_name}' returned '{output}'. No route mapping matched. Ending Execution.")
                    break
                
                current_node_name = next_node_name
            else:
                edges = self.graph.edges.get(current_node_name, [])
                if not edges:
                    break
                
                current_node_name = edges[0]
                if len(edges) > 1:
                    logger.warning(f"Multiple edges from '{node.name}', but running sequentially. Selected '{current_node_name}'.")

        total_duration = time.time() - start_time
        StorageRegistry.save_trace(run_id, execution_trace)
        MetricsRegistry.record_run(total_duration)
        PluginManager.on_run_end(run_id, self.graph, current_input)
        
        # Persist memory for future turns
        if session_id:
            MemoryStore.save_state(session_id, state.to_dict())
        
        logger.info(f"Execution run completed in {total_duration:.3f}s")
        return current_input

import asyncio

class AsyncExecutor:
    """Runs a graph asynchronously, supporting parallel node execution fan-out and real-time streaming."""
    
    def __init__(self, graph: Graph):
        self.graph = graph

    async def execute(self, input_data: Any = None, run_id: str = None, session_id: str = None) -> Any:
        """Helper to run the stream until finish and return the final output."""
        last_output = input_data
        async for event in self.astream(input_data, run_id, session_id):
            if event["type"] == "node_end":
                last_output = event["output"]
            elif event["type"] == "interrupt":
                logger.warning(f"Execution interrupted at node(s): {event['nodes']}")
                return last_output
        return last_output

    async def astream(self, input_data: Any = None, run_id: str = None, session_id: str = None):
        """Yields execution events iteratively and executes parallel branches via asyncio.gather."""
        run_id = run_id or str(uuid.uuid4())
        
        initial_data = MemoryStore.get_state(session_id) if session_id else {}
        state = GraphState(initial_data, schema=self.graph.state_schema)
        
        try:
            state.validate()
        except ValueError as e:
            logger.error(f"Initial state schema rejected: {e}")
            raise RuntimeError(f"Cannot start execution: {e}")
            
        active_nodes = [(self.graph.entrypoint, input_data)] if self.graph.entrypoint else []
        execution_trace = []
        
        logger.info(f"Starting async execution run: {run_id} (Session: {session_id or 'Anonymous'})")
        start_time = time.time()
        PluginManager.on_run_start(run_id, self.graph, input_data)

        while active_nodes:
            executable = []
            interrupted = []
            
            for node_name, node_input in active_nodes:
                if node_name in self.graph.interrupt_before:
                    interrupted.append(node_name)
                else:
                    executable.append((node_name, node_input))
                    
            if not executable:
                if interrupted:
                    if session_id:
                        MemoryStore.save_state(session_id, state.to_dict())
                    yield {"type": "interrupt", "nodes": interrupted, "state": state.to_dict()}
                break

            # Fire concurrent execution of all active nodes in this topological layer
            tasks = [self._arun_node(name, inp, state, run_id, execution_trace) for name, inp in executable]
            results = await asyncio.gather(*tasks)
            
            # Yield layer completion
            for res in results:
                yield {"type": "node_end", "node": res["node"], "output": res["output"], "state": state.to_dict()}

            next_layer = []
            for res in results:
                node_name = res["node"]
                output = res["output"]
                status = res["status"]
                
                if status == "error":
                    if session_id:
                        MemoryStore.save_state(session_id, state.to_dict())
                    raise RuntimeError(f"Async execution failed at node '{node_name}': {res.get('error')}")

                if hasattr(self.graph, "routes") and node_name in self.graph.routes:
                    route_mapping = self.graph.routes[node_name]
                    next_node = route_mapping.get(output)
                    if next_node:
                        next_layer.append((next_node, output))
                    else:
                        logger.debug(f"Routing node '{node_name}' returned '{output}'. No route found.")
                else:
                    edges = self.graph.edges.get(node_name, [])
                    for edge in edges:
                        next_layer.append((edge, output))
                        
            active_nodes = next_layer

        total_duration = time.time() - start_time
        StorageRegistry.save_trace(run_id, execution_trace)
        MetricsRegistry.record_run(total_duration)
        PluginManager.on_run_end(run_id, self.graph, None)
        
        if session_id:
            MemoryStore.save_state(session_id, state.to_dict())
            
        logger.info(f"Async execution run completed in {total_duration:.3f}s")


    async def _arun_node(self, node_name: str, current_input: Any, state: GraphState, run_id: str, execution_trace: list):
        node = self.graph.nodes.get(node_name)
        if not node:
            raise RuntimeError(f"Unregistered node '{node_name}'")
            
        node_start = time.time()
        logger.debug(f"Async executing node: {node_name}")
        PluginManager.on_node_start(run_id, node, current_input, state)

        try:
            output = await node.aexecute(current_input, state)
            status = "success"
            error = None
        except Exception as e:
            output = None
            status = "error"
            error = str(e)
            logger.error(f"Node async execution failed: {e}")

        node_duration = time.time() - node_start
        
        step_trace = {
            "step": len(execution_trace) + 1,
            "node": node_name,
            "input": current_input,
            "output": output,
            "state_snapshot": state.to_dict(),
            "duration": node_duration,
            "status": status,
            "error": error
        }
        execution_trace.append(step_trace)
        
        MetricsRegistry.record_node_execution(node_name, node_duration)
        PluginManager.on_node_end(run_id, node, output, state)
        
        return {"node": node_name, "output": output, "status": status, "error": error}
