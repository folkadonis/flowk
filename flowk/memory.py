from typing import Dict

class MemoryStore:
    """
    Manages long-term state persistence across multiple execution runs.
    Allows for multi-turn conversational agents or step-by-step stateful workflows.
    """
    _sessions: Dict[str, dict] = {}

    @classmethod
    def get_state(cls, session_id: str) -> dict:
        """Retrieves the last known state dictionary for a specific session."""
        return cls._sessions.get(session_id, {})

    @classmethod
    def save_state(cls, session_id: str, state_dict: dict):
        """Saves the graph state for a session."""
        cls._sessions[session_id] = state_dict

    @classmethod
    def clear(cls, session_id: str = None):
        if session_id:
            cls._sessions.pop(session_id, None)
        else:
            cls._sessions.clear()
