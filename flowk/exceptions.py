class GraphError(Exception):
    """Base exception for all graph-related errors."""
    pass

class NodeExecutionError(GraphError):
    """Raised when a node fails to execute after all retries."""
    pass

class InvalidGraphError(GraphError):
    """Raised when the graph structure is invalid."""
    pass

class ReplayError(GraphError):
    """Raised when an execution trace cannot be replayed."""
    pass
