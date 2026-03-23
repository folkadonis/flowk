import json
from typing import Any, Optional

try:
    from fastapi import FastAPI, Request, HTTPException  # pyre-ignore
    from fastapi.responses import StreamingResponse, FileResponse  # pyre-ignore
    from fastapi.staticfiles import StaticFiles  # pyre-ignore
    import uvicorn  # pyre-ignore
    import os
    _fastapi_available = True
except ImportError:
    _fastapi_available = False


def create_app(graph: Any) -> Any:
    """
    Dynamically generates a FastAPI application tailored to the provided Flowk Graph.
    Uses the graph's `state_schema` if provided to generate OpenAPI docs.
    """
    if not _fastapi_available:  # pyre-ignore
        raise ImportError(
            "FastAPI and Uvicorn are required to call create_app. "
            "Install them via: pip install 'flowk[api]'"
        )

    app = FastAPI(  # pyre-ignore
        title="Flowk API",
        description="Auto-generated API for your Flowk Agent",
        version="0.3.0",
    )

    # ------------------------------------------------------------------
    # Static UI Assets
    # ------------------------------------------------------------------
    ui_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "ui", "v2", "dist"))
    print(f"📂 UI Assets Directory: {ui_dist}")
    
    if os.path.exists(ui_dist):
        print("✅ UI Assets found. Registering routes.")
        app.mount("/assets", StaticFiles(directory=os.path.join(ui_dist, "assets")), name="assets")

        @app.get("/")
        async def serve_ui():
            index_path = os.path.join(ui_dist, "index.html")
            if not os.path.exists(index_path):
                print(f"❌ index.html NOT FOUND at {index_path}")
                raise HTTPException(status_code=404, detail="index.html not found")
            return FileResponse(index_path)
    else:
        print(f"❌ UI Assets NOT FOUND at {ui_dist}")

    @app.post("/invoke")  # pyre-ignore
    async def invoke(request: Request) -> dict:  # pyre-ignore
        """
        Standard request-response execution.
        Provide JSON payload: {"input": ..., "session_id": "optional", "state": {}}
        """
        data = await request.json()
        input_data: Any = data.get("input", None)
        session_id: Optional[str] = data.get("session_id", None)
        initial_state: Optional[dict] = data.get("state", {})

        try:
            result = await graph.arun(
                input_data=input_data,
                session_id=session_id,
                initial_state=initial_state,
            )
            return {"status": "success", "result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))  # pyre-ignore

    @app.post("/stream")  # pyre-ignore
    async def stream(request: Request) -> Any:  # pyre-ignore
        """
        Server-Sent Events (SSE) streaming endpoint.
        Yields execution events in real-time.
        """
        data = await request.json()
        input_data: Any = data.get("input", None)
        session_id: Optional[str] = data.get("session_id", None)
        initial_state: Optional[dict] = data.get("state", {})

        async def event_generator():
            try:
                async for event in graph.astream(
                    input_data=input_data,
                    session_id=session_id,
                    initial_state=initial_state,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")  # pyre-ignore

    @app.post("/async")
    async def invoke_async(request: Request) -> dict:
        """
        Trigger execution on a background task.
        Returns the run_id immediately.
        """
        import uuid
        import asyncio
        data = await request.json()
        input_data = data.get("input", None)
        session_id = data.get("session_id", None)
        initial_state = data.get("state", {})
        run_id = str(uuid.uuid4())

        # Start background task
        asyncio.create_task(
            graph.arun(
                input_data=input_data,
                run_id=run_id,
                session_id=session_id,
                initial_state=initial_state,
            )
        )

        return {"status": "accepted", "run_id": run_id}

    @app.get("/status/{run_id}")
    async def get_status(run_id: str):
        """Check the current status of a background run based on its latest events."""
        from flowk.storage import StorageRegistry
        events = StorageRegistry.get_events(run_id)
        if not events:
            # Check if it finished and was archived in trace
            trace = StorageRegistry.get_trace(run_id)
            if trace:
                return {"status": "completed", "progress": "Execution archived"}
            return {"status": "pending", "progress": "No events recorded yet"}
        
        last_event = events[-1]
        return {
            "status": "running" if last_event["type"] not in ["run_end", "run_error", "run_interrupt"] else "finished",
            "last_node": last_event["node"],
            "last_type": last_event["type"],
            "timestamp": last_event["timestamp"]
        }

    # ------------------------------------------------------------------
    # UI / Observability Endpoints
    # ------------------------------------------------------------------

    @app.get("/ui/sessions")
    async def get_sessions():
        """List all active sessions and their latest state snapshots."""
        from flowk.memory import MemoryStore
        return MemoryStore.list_sessions()

    @app.get("/ui/runs")
    async def get_runs(session_id: Optional[str] = None):
        """List all recorded execution run IDs, optional filter by session."""
        from flowk.storage import StorageRegistry
        return StorageRegistry.list_runs(session_id=session_id)

    @app.get("/ui/session/{session_id}/runs")
    async def get_session_runs(session_id: str):
        """List all run IDs for a specific session."""
        from flowk.storage import StorageRegistry
        return StorageRegistry.list_runs(session_id=session_id)

    @app.get("/ui/run/{run_id}")
    async def get_run_trace(run_id: str):
        """Retrieve the full step-by-step execution trace for a specific run."""
        from flowk.storage import StorageRegistry
        try:
            return StorageRegistry.get_trace(run_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.get("/ui/graph")
    async def get_graph():
        """Export graph topology for UI visualization."""
        from flowk.storage import StorageRegistry
        
        # Try finding persisted graph first if local graph is dummy
        if not graph.nodes:
            persisted = StorageRegistry.get_graph("default")
            if persisted:
                return persisted

        nodes = [{"id": n.name, "name": n.name, "type": "agent" if "agent" in n.name.lower() else "node"} for n in graph.nodes.values()]
        edges = []
        for src, targets in graph.edges.items():
            for tgt in targets:
                edges.append({"source": src, "target": tgt, "type": "flow"})
        for src, mapping in graph.routes.items():
            for val, tgt in mapping.items():
                edges.append({"source": src, "target": tgt, "type": "route", "label": str(val)})
        return {"nodes": nodes, "edges": edges}

    @app.get("/ui/run/{run_id}/events")
    async def get_run_events(run_id: str):
        """Retrieve the immutable event log for a specific run (Event Sourcing)."""
        from flowk.storage import StorageRegistry
        try:
            return StorageRegistry.get_events(run_id)
        except Exception as e:
            raise HTTPException(status_code=404, detail=str(e))

    return app
