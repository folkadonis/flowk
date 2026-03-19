import json
import sqlite3
from typing import Any, ClassVar, Dict, Optional


class MemoryStore:
    """
    Manages long-term state persistence across multiple execution runs.
    Supports three backends:
      - In-Memory  (default, no config needed)
      - SQLite     configure("path/to/db.sqlite")
      - Redis      configure("redis://localhost:6379/0")  [requires flowk[redis]]
    """

    # ClassVar prevents these from being treated as instance attributes
    _sessions: ClassVar[Dict[str, dict]] = {}
    _db_path: ClassVar[Optional[str]] = None
    _redis_client: ClassVar[Optional[Any]] = None  # Any avoids hard redis dependency

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @classmethod
    def configure(cls, connection_string: Optional[str] = None) -> None:
        """
        Set up the persistence backend. Call once at startup.

        Args:
            connection_string:  SQLite file path  e.g. "flowk.db"
                                Redis URL         e.g. "redis://localhost:6379/0"
                                None              uses in-memory dict (default)
        """
        if not connection_string:
            return

        if connection_string.startswith("redis://"):
            try:
                import redis  # type: ignore  # pyre-ignore
            except ImportError:
                raise ImportError(
                    "Redis is required for this backend. "
                    "Install it with: pip install 'flowk[redis]'"
                )
            # Local assignment ensures static analyzers see a strong type
            client: Any = redis.from_url(connection_string)  # type: ignore  # pyre-ignore
            cls._redis_client = client
        else:
            cls._db_path = connection_string
            # Local assignment forces the linter to narrow from Optional[str] to str
            db_path: str = connection_string
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS sessions "
                    "(id TEXT PRIMARY KEY, state TEXT)"
                )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @classmethod
    def get_state(cls, session_id: str) -> dict:
        """Return the last persisted state dict for *session_id*, or {} if none."""
        # Use local variables to statically resolve type narrowing for IDE linters
        redis_client: Any = cls._redis_client
        if redis_client is not None:
            raw = redis_client.get(f"flowk:session:{session_id}")
            return json.loads(raw) if raw else {}

        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT state FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
            return json.loads(row[0]) if row else {}

        # In-memory fallback
        return cls._sessions.get(session_id, {})

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @classmethod
    def save_state(cls, session_id: str, state_dict: dict) -> None:
        """Persist *state_dict* under *session_id*."""
        redis_client: Any = cls._redis_client
        if redis_client is not None:
            redis_client.set(
                f"flowk:session:{session_id}", json.dumps(state_dict)
            )
            return

        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO sessions (id, state) VALUES (?, ?)",
                    (session_id, json.dumps(state_dict)),
                )
            return

        # In-memory fallback
        cls._sessions[session_id] = state_dict

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    @classmethod
    def clear(cls, session_id: Optional[str] = None) -> None:
        """
        Delete persisted state.

        Args:
            session_id: If given, delete only that session.
                        If None, wipe all sessions.
        """
        redis_client: Any = cls._redis_client
        if redis_client is not None:
            if session_id:
                redis_client.delete(f"flowk:session:{session_id}")
            else:
                keys = redis_client.keys("flowk:session:*")
                if keys:
                    redis_client.delete(*keys)
            return

        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                if session_id:
                    conn.execute(
                        "DELETE FROM sessions WHERE id = ?", (session_id,)
                    )
                else:
                    conn.execute("DELETE FROM sessions")
            return

        # In-memory fallback
        if session_id:
            cls._sessions.pop(session_id, None)
        else:
            cls._sessions.clear()

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @classmethod
    def reset(cls) -> None:
        """
        Full reset: clear all state AND drop the configured backend.
        Useful in tests to avoid state leaking between runs.
        """
        cls._sessions = {}
        cls._db_path = None
        cls._redis_client = None
