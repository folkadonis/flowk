import time
from typing import Any
from flowk.plugins.base import Plugin
from flowk.metrics import MetricsRegistry

class LLMTokenTrackerPlugin(Plugin):
    """
    A mock plugin representing how an LLM integration would hook into the graph lifecycle.
    It simulates tracking token usage on node end if specific metrics are found in output.
    """
    def on_node_end(self, run_id: str, node: Any, output_data: Any, state: Any):
        if isinstance(output_data, dict):
            p_tokens = output_data.get("prompt_tokens", 0)
            c_tokens = output_data.get("completion_tokens", 0)
            
            if p_tokens or c_tokens:
                # Mock cost model
                cost = (p_tokens / 1000) * 0.001 + (c_tokens / 1000) * 0.002
                MetricsRegistry.track_llm_call(p_tokens, c_tokens, cost)
