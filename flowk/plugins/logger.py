import logging
from typing import Any, Dict
from flowk.plugins.base import Plugin  # pyre-ignore

class LoggerPlugin(Plugin):
    """
    A plugin that streams structured JSON-like telemetry to the standard logger
    at every node transition, providing out-of-the-box observability for production deployments.
    """
    def __init__(self, log_level: int = logging.INFO):
        self.logger = logging.getLogger("flowk.telemetry")
        if not self.logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(log_level)
        self.logger.propagate = False

    def on_run_start(self, run_id: str, graph: Any, input_data: Any):
        self.logger.info(f"[RUN_START] run_id={run_id} entrypoint={graph.entrypoint}")

    def on_node_start(self, run_id: str, node: Any, input_data: Any, state: Any):
        # We try to avoid logging massive state footprints, just the keys
        state_keys = list(state.keys()) if isinstance(state, dict) else []
        self.logger.info(f"[NODE_START] run_id={run_id} node={node.name} state_keys={state_keys}")

    def on_node_end(self, run_id: str, node: Any, output_data: Any, state: Any):
        status = "success"
        if isinstance(output_data, dict) and output_data.get("error"):
             status = "error"
        self.logger.info(f"[NODE_END] run_id={run_id} node={node.name} status={status}")

    def on_run_end(self, run_id: str, graph: Any, output_data: Any):
        self.logger.info(f"[RUN_END] run_id={run_id} output_type={type(output_data).__name__}")
