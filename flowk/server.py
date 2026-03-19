import json
from typing import Any, Optional

try:
    from fastapi import FastAPI, Request, HTTPException  # pyre-ignore
    from fastapi.responses import StreamingResponse  # pyre-ignore
    import uvicorn  # pyre-ignore
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

    return app
