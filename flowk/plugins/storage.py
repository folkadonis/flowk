import json
import os
from typing import Any
from flowk.plugins.base import Plugin
from flowk.utils import serialize_for_log

class FileStoragePlugin(Plugin):
    """
    Persists run traces to a local log file on the disk at the end of each run.
    """
    def __init__(self, log_file: str = "flowk_runs.log"):
        self.log_file = log_file

    def on_run_end(self, run_id: str, graph: Any, output_data: Any):
        from flowk.storage import StorageRegistry
        try:
            trace = StorageRegistry.get_trace(run_id)
            record = {
                "run_id": run_id,
                "final_output": serialize_for_log(output_data),
                "trace": trace
            }
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            # Swallow error to not interrupt the graph's main flow
            print(f"FileStoragePlugin Error: {e}")
