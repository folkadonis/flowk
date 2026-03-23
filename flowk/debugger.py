import time
import uuid
from typing import Any, Optional

from flowk.graph import Graph
from flowk.storage import StorageRegistry
from flowk.plugins.base import PluginManager, DebugPlugin
from flowk.executor import SequentialExecutor

class Debugger:
    def __init__(self, graph: Graph):
        self.graph = graph

    def run(self, input_data: Any, session_id: Optional[str] = None) -> Any:
        uid_str = str(uuid.uuid4()).replace("-", "")
        run_id = f"debug_{uid_str[:8]}"
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
        print(f"\n⏪ INTERACTIVE TIME-TRAVEL REPLAY: {run_id}")
        print("="*60)
        trace = StorageRegistry.get_trace(run_id)
        
        if not trace:
            print(f"❌ No historical trace found for {run_id}.")
            return
            
        print("Press [Enter] to step through history chronologically...")
        
        prev_state = {}
        for step in trace:
            input(f"\n👉 [Press Enter for Step {step['step']}: Node '{step['node']}'] ")
            
            print(f"  📥 Input:  {step.get('input')}")
            
            curr_state = step.get('state_snapshot', {})
            
            # Calculate dict diff
            added = {k: v for k, v in curr_state.items() if k not in prev_state}
            removed = {k: v for k, v in prev_state.items() if k not in curr_state}
            modified = {k: (prev_state[k], curr_state[k]) for k in curr_state if k in prev_state and prev_state[k] != curr_state[k]}
            
            if added or removed or modified:
                print("  🔀 State Diff:")
                for k, v in added.items(): print(f"     [+] {k}: {v}")
                for k, v in removed.items(): print(f"     [-] {k}: {v}")
                for k, (old, new) in modified.items(): print(f"     [~] {k}: {old} -> {new}")
            else:
                print("  🔀 State Diff: [No Changes]")
                
            prev_state = curr_state
            
            print(f"  ⚙️ Status: {step['status']}")
            
            if step['status'] == 'error':
                print(f"  ❌ Error:  {step['error']}")
            else:
                print(f"  📤 Output: {step.get('output')}")
            print(f"  ⏱️ Duration: {step.get('duration', 0):.4f}s")
            
        print("\n" + "="*60)
        print("⏹️ REPLAY COMPLETE\n")

    def step(self, input_data: Any):
        """Interactive stepping generator (v1 simple console input)."""
        uid_str = str(uuid.uuid4()).replace("-", "")
        run_id = f"step_{uid_str[:8]}"
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
