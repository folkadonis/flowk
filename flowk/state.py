class GraphState:
    """
    Shared state dictionary passed across all nodes in the graph.
    Nodes can read from and mutate this state.
    """
    def __init__(self, initial_state=None, schema=None):
        self._data = initial_state or {}
        self.schema = schema

    def validate(self):
        """Enforces schema matching if a Pydantic schema is bound."""
        if self.schema is not None:
            try:
                # Type safe runtime validation
                validated = self.schema(**self._data)
                
                # Support Pydantic v1 and v2 dump mechanisms
                if hasattr(validated, "model_dump"):
                    self._data = validated.model_dump()
                elif hasattr(validated, "dict"):
                    self._data = validated.dict()
            except Exception as e:
                # We throw a broad exception so the Executor catches validation failures natively
                raise ValueError(f"State Schema Validation Failed: {e}")

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def update(self, other_dict):
        self._data.update(other_dict)

    def to_dict(self):
        return self._data.copy()

    def __repr__(self):
        return f"GraphState({self._data})"
