import json
import sqlite3
from typing import Dict, Any, Optional

class MemoryStore:
    """
    Manages long-term state persistence across multiple execution runs.
    """
    _sessions: Dict[str, dict] = {}
    _db_path: Optional[str] = None

    @classmethod
    def configure(cls, db_path: str = None):
        """Sets up persistent storage if a path is provided."""
        cls._db_path = db_path
        if db_path:
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT)")

    @classmethod
    def get_state(cls, session_id: str) -> dict:
        """Retrieves the last known state dictionary for a specific session."""
        if not cls._db_path:
            return cls._sessions.get(session_id, {})
        
        with sqlite3.connect(cls._db_path) as conn:
            row = conn.execute("SELECT state FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return json.loads(row[0]) if row else {}

    @classmethod
    def save_state(cls, session_id: str, state_dict: dict):
        """Saves the graph state for a session."""
        if not cls._db_path:
            cls._sessions[session_id] = state_dict
            return

        state_json = json.dumps(state_dict)
        with sqlite3.connect(cls._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (id, state) VALUES (?, ?)", 
                (session_id, state_json)
            )

    @classmethod
    def clear(cls, session_id: str = None):
        if not cls._db_path:
            if session_id:
                cls._sessions.pop(session_id, None)
            else:
                cls._sessions.clear()
            return

        with sqlite3.connect(cls._db_path) as conn:
            if session_id:
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            else:
                conn.execute("DELETE FROM sessions")
