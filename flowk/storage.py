import json
import sqlite3
from typing import Dict, List, Any, Optional
from flowk.exceptions import ReplayError

class StorageRegistry:
    """Persistent trace storage for Run observability and Time Travel features."""
    _traces: Dict[str, List[Dict[str, Any]]] = {}
    _db_path: Optional[str] = None
    _redis_client: Optional[Any] = None

    @classmethod
    def configure(cls, connection_string: Optional[str] = None) -> None:
        """Set up the persistence backend for traces."""
        import os
        
        # Default to .flowk/flowk.db if no connection string is provided
        if not connection_string:
            connection_string = os.path.join(os.getcwd(), ".flowk", "flowk.db")

        if connection_string.startswith("redis://"):
            import redis
            cls._redis_client = redis.from_url(connection_string)
        else:
            cls._db_path = connection_string
            db_dir = os.path.dirname(connection_string)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                
            with sqlite3.connect(connection_string) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS runs "
                    "(id TEXT PRIMARY KEY, session_id TEXT, trace TEXT)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS graphs "
                    "(id TEXT PRIMARY KEY, data TEXT)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS events "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, session_id TEXT, node TEXT, type TEXT, data TEXT, timestamp REAL)"
                )

    @classmethod
    def save_trace(cls, run_id: str, trace: List[Dict[str, Any]], session_id: Optional[str] = None):
        """Persist execution trace associated with a run (and optionally a session)."""
        redis_client: Any = cls._redis_client
        if redis_client is not None:
            data = {"session_id": session_id, "trace": trace}
            redis_client.set(f"flowk:run:{run_id}", json.dumps(data))
            if session_id:
                redis_client.sadd(f"flowk:session_runs:{session_id}", run_id)
            return

        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO runs (id, session_id, trace) VALUES (?, ?, ?)",
                    (run_id, session_id, json.dumps(trace)),
                )
            return

        cls._traces[run_id] = trace

    @classmethod
    def get_trace(cls, run_id: str) -> List[Dict[str, Any]]:
        """Retrieve trace for a specific execution run."""
        redis_client: Any = cls._redis_client
        if redis_client is not None:
            raw = redis_client.get(f"flowk:run:{run_id}")
            return json.loads(raw)["trace"] if raw else None

        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT trace FROM runs WHERE id = ?", (run_id,)).fetchone()
            return json.loads(row[0]) if row else None

        trace = cls._traces.get(run_id)
        if trace is None:
            raise ReplayError(f"No run trace found for ID: {run_id}")
        return trace

    @classmethod
    def list_runs(cls, session_id: Optional[str] = None) -> List[str]:
        """List all run IDs, optionally filtered by session_id."""
        redis_client: Any = cls._redis_client
        if redis_client is not None:
            if session_id:
                keys = redis_client.smembers(f"flowk:session_runs:{session_id}")
                return [k.decode("utf-8") for k in keys]
            keys = redis_client.keys("flowk:run:*")
            return [k.decode("utf-8").replace("flowk:run:", "") for k in keys]

        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                if session_id:
                    rows = conn.execute("SELECT id FROM runs WHERE session_id = ?", (session_id,)).fetchall()
                else:
                    rows = conn.execute("SELECT id FROM runs").fetchall()
            return [row[0] for row in rows]

        return list(cls._traces.keys())

    @classmethod
    def save_graph(cls, graph_id: str, data: Dict[str, Any]):
        """Persist graph topology (nodes and edges)."""
        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO graphs (id, data) VALUES (?, ?)",
                    (graph_id, json.dumps(data)),
                )
            return
        cls._traces[f"graph:{graph_id}"] = [data] # fallback

    @classmethod
    def get_graph(cls, graph_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve persisted graph topology."""
        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT data FROM graphs WHERE id = ?", (graph_id,)).fetchone()
            return json.loads(row[0]) if row else None
        return None

    @classmethod
    def save_event(cls, run_id: str, event_type: str, node: Optional[str], data: Any, session_id: Optional[str] = None):
        """Record a discrete execution event (Event Sourcing)."""
        import time
        event = {
            "run_id": run_id,
            "session_id": session_id,
            "node": node,
            "type": event_type,
            "data": data,
            "timestamp": time.time()
        }

        redis_client: Any = cls._redis_client
        if redis_client is not None:
            redis_client.rpush(f"flowk:events:{run_id}", json.dumps(event))
            return

        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "INSERT INTO events (run_id, session_id, node, type, data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (run_id, session_id, node, event_type, json.dumps(data), event["timestamp"])
                )
            return

        # In-memory fallback
        if "events" not in cls._traces:
            cls._traces["events"] = []  # pyre-ignore
        cls._traces["events"].append(event)  # pyre-ignore

    @classmethod
    def get_events(cls, run_id: str) -> List[Dict[str, Any]]:
        """Retrieve all events for a specific run."""
        redis_client: Any = cls._redis_client
        if redis_client is not None:
            raw_events = redis_client.lrange(f"flowk:events:{run_id}", 0, -1)
            return [json.loads(e) for e in raw_events]

        db_path: Optional[str] = cls._db_path
        if db_path is not None:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT run_id, session_id, node, type, data, timestamp FROM events WHERE run_id = ? ORDER BY id ASC",
                    (run_id,)
                ).fetchall()
                return [
                    {"run_id": r[0], "session_id": r[1], "node": r[2], "type": r[3], "data": json.loads(r[4]), "timestamp": r[5]}
                    for r in rows
                ]

        return [e for e in cls._traces.get("events", []) if e["run_id"] == run_id]

    @classmethod
    def clear(cls):
        """Clear all in-memory traces and events."""
        cls._traces.clear()
