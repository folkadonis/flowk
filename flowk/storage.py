from typing import Dict, List, Any
from flowk.exceptions import ReplayError

class StorageRegistry:
    """In-memory trace storage for Run observability and Time Travel features."""
    _traces: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    def save_trace(cls, run_id: str, trace: List[Dict[str, Any]]):
        cls._traces[run_id] = trace

    @classmethod
    def get_trace(cls, run_id: str) -> List[Dict[str, Any]]:
        trace = cls._traces.get(run_id)
        if trace is None:
            raise ReplayError(f"No run trace found for ID: {run_id}")
        return trace

    @classmethod
    def list_runs(cls) -> List[str]:
        return list(cls._traces.keys())

    @classmethod
    def clear(cls):
        cls._traces.clear()
