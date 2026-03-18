import json
import sqlite3
import redis
from typing import Dict, Any, Optional, Union

class MemoryStore:
    """
    Manages long-term state persistence across multiple execution runs.
    Supports In-Memory, SQLite, and Redis backends.
    """
    _sessions: Dict[str, dict] = {}
    _db_path: Optional[str] = None
    _redis_client: Optional[redis.Redis] = None

    @classmethod
    def configure(cls, connection_string: str = None):
        """
        Sets up persistent storage.
        - sqlite: "path/to/db.sqlite"
        - redis: "redis://localhost:6379/0"
        """
        if not connection_string:
            return

        if connection_string.startswith("redis://"):
            cls._redis_client = redis.from_url(connection_string)
        else:
            cls._db_path = connection_string
            with sqlite3.connect(cls._db_path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT)")

    @classmethod
    def get_state(cls, session_id: str) -> dict:
        """Retrieves the last known state dictionary for a specific session."""
        if cls._redis_client:
            data = cls._redis_client.get(f"flowk:session:{session_id}")
            return json.loads(data) if data else {}
            
        if not cls._db_path:
            return cls._sessions.get(session_id, {})
        
        with sqlite3.connect(cls._db_path) as conn:
            row = conn.execute("SELECT state FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return json.loads(row[0]) if row else {}

    @classmethod
    def save_state(cls, session_id: str, state_dict: dict):
        """Saves the graph state for a session."""
        if cls._redis_client:
            cls._redis_client.set(f"flowk:session:{session_id}", json.dumps(state_dict))
            return

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
        if cls._redis_client:
            if session_id:
                cls._redis_client.delete(f"flowk:session:{session_id}")
            else:
                # Warning: flushdb counterpart might be too aggressive, just delete flowk keys
                keys = cls._redis_client.keys("flowk:session:*")
                if keys: cls._redis_client.delete(*keys)
            return

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
