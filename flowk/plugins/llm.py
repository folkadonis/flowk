import time
from typing import Any, Optional
from flowk.plugins.base import Plugin
from flowk.metrics import MetricsRegistry

class OpenAIPlugin(Plugin):
    """
    Native OpenAI integration for Flowk.
    Automatically captures token usage and cost metrics.
    """
    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        # Prices per 1k tokens (Example)
        self.prices = {"gpt-4o": (0.005, 0.015), "gpt-3.5-turbo": (0.0005, 0.0015)}

    def on_node_end(self, node_name: str, output: Any, state: Any):
        if isinstance(output, dict) and "usage" in output:
            usage = output["usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            
            p_price, c_price = self.prices.get(self.model, (0, 0))
            cost = (prompt_tokens / 1000 * p_price) + (completion_tokens / 1000 * c_price)
            
            MetricsRegistry.track_llm_call(prompt_tokens, completion_tokens, cost)

class AnthropicPlugin(Plugin):
    """
    Native Anthropic integration for Flowk.
    """
    def __init__(self, model: str = "claude-3-opus", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key

    def on_node_end(self, node_name: str, output: Any, state: Any):
        pass
