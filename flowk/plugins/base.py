from typing import List, Any
import time

class Plugin:
    """Base class for all flowk plugins."""
    def on_run_start(self, run_id: str, graph: Any, input_data: Any): pass
    def on_node_start(self, run_id: str, node: Any, input_data: Any, state: Any): pass
    def on_node_end(self, run_id: str, node: Any, output_data: Any, state: Any): pass
    def on_run_end(self, run_id: str, graph: Any, output_data: Any): pass

class PluginManagerClass:
    """Global manager orchestrating plugin hooks during graph execution."""
    def __init__(self):
        self.plugins: List[Plugin] = []
        
    def register(self, plugin: Plugin):
        self.plugins.append(plugin)
        
    def clear(self):
        self.plugins.clear()
        
    def on_run_start(self, run_id: str, graph: Any, input_data: Any):
        for p in self.plugins: p.on_run_start(run_id, graph, input_data)
        
    def on_node_start(self, run_id: str, node: Any, input_data: Any, state: Any):
        for p in self.plugins: p.on_node_start(run_id, node, input_data, state)
        
    def on_node_end(self, run_id: str, node: Any, output_data: Any, state: Any):
        for p in self.plugins: p.on_node_end(run_id, node, output_data, state)
        
    def on_run_end(self, run_id: str, graph: Any, output_data: Any):
        for p in self.plugins: p.on_run_end(run_id, graph, output_data)

PluginManager = PluginManagerClass()

class DebugPlugin(Plugin):
    """A built-in plugin attached when graph.debug() is called, providing noisy prints."""
    def on_run_start(self, run_id, graph, input_data):
        print("\n" + "="*50)
        print(f"🚀 flowk DEBUG RUN STARTED (ID: {run_id})")
        print("="*50)
        print(f"[{time.strftime('%H:%M:%S')}] 📥 INITIAL INPUT: {input_data}")
        
    def on_node_start(self, run_id, node, input_data, state):
        print(f"\n[{time.strftime('%H:%M:%S')}] ⚡ EXECUTING NODE: '{node.name}'")
        print(f"  ├─ Input: {input_data}")
        print(f"  ├─ State: {state.to_dict()}")

    def on_node_end(self, run_id, node, output_data, state):
        print(f"  └─ Output: {output_data}")

    def on_run_end(self, run_id, graph, output_data):
        print("\n" + "="*50)
        print(f"[{time.strftime('%H:%M:%S')}] 🏁 FINAL OUTPUT: {output_data}")
        print("="*50 + "\n")
