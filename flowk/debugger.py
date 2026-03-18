import time
import uuid
from typing import Any

from flowk.graph import Graph
from flowk.storage import StorageRegistry
from flowk.plugins.base import PluginManager, DebugPlugin
from flowk.executor import SequentialExecutor

class Debugger:
    def __init__(self, graph: Graph):
        self.graph = graph

    def run(self, input_data: Any, session_id: str = None) -> Any:
        run_id = f"debug_{uuid.uuid4().hex[:8]}"
        debug_plugin = DebugPlugin()
        
        # Attach strictly for this run
        PluginManager.register(debug_plugin)
        try:
            executor = SequentialExecutor(self.graph)
            return executor.execute(input_data, run_id=run_id, session_id=session_id)
        finally:
            # Cleanup plugin so subsequent graph.run() goes silent
            PluginManager.plugins.remove(debug_plugin)

    def replay(self, run_id: str):
        print(f"\n⏪ REPLAYING RUN: {run_id}")
        print("="*50)
        trace = StorageRegistry.get_trace(run_id)
        
        for step in trace:
            print(f"\nStep {step['step']}: Node '{step['node']}'")
            print(f"  Input:  {step['input']}")
            print(f"  State:  {step['state_snapshot']}")
            print(f"  Status: {step['status']}")
            
            if step['status'] == 'error':
                print(f"  Error:  {step['error']}")
            else:
                print(f"  Output: {step['output']}")
            print(f"  Duration: {step['duration']:.4f}s")
            time.sleep(0.5)
            
        print("\n" + "="*50)
        print("⏹️ REPLAY COMPLETE\n")

    def step(self, input_data: Any):
        """Interactive stepping generator (v1 simple console input)."""
        run_id = f"step_{uuid.uuid4().hex[:8]}"
        executor = SequentialExecutor(self.graph)
        
        print("\n" + "="*50)
        print("👞 STEP DEBUGGER STARTED")
        print("="*50)
        
        # We hook into nodes via a custom plugin
        class SteppingPlugin(DebugPlugin):
            def on_node_start(self, run_id, node, input_data, state):
                super().on_node_start(run_id, node, input_data, state)
                input("\n[Press Enter to execute this node...]")
        
        step_plugin = SteppingPlugin()
        PluginManager.register(step_plugin)
        try:
            return executor.execute(input_data, run_id=run_id)
        finally:
            PluginManager.plugins.remove(step_plugin)
