class MetricsRegistry:
    """Singleton for tracking graph metrics incrementally across runs."""
    _node_times = {}
    _run_times = []
    _token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    _cost = 0.0

    @classmethod
    def record_node_execution(cls, node_name: str, duration: float):
        if node_name not in cls._node_times:
            cls._node_times[node_name] = []
        cls._node_times[node_name].append(duration)

    @classmethod
    def record_run(cls, duration: float):
        cls._run_times.append(duration)

    @classmethod
    def track_llm_call(cls, prompt_tokens: int, completion_tokens: int, cost: float = 0.0):
        cls._token_usage["prompt_tokens"] += prompt_tokens
        cls._token_usage["completion_tokens"] += completion_tokens
        cls._token_usage["total_tokens"] += (prompt_tokens + completion_tokens)
        cls._cost += cost

    @classmethod
    def get_summary(cls):
        summary = {
            "total_runs": len(cls._run_times),
            "avg_run_time": sum(cls._run_times)/len(cls._run_times) if cls._run_times else 0,
            "node_metrics": {},
            "llm_metrics": {
                "tokens": dict(cls._token_usage),
                "estimated_cost_usd": cls._cost
            }
        }
        for name, times in cls._node_times.items():
            summary["node_metrics"][name] = {
                "calls": len(times),
                "avg_time": sum(times)/len(times)
            }
        return summary
    
    @classmethod
    def clear(cls):
        cls._node_times.clear()
        cls._run_times.clear()
        cls._token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        cls._cost = 0.0
