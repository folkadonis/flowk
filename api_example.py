import asyncio
from flowk import Graph  # pyre-ignore
from pydantic import BaseModel  # pyre-ignore

class AgentState(BaseModel):
    message: str
    reply: str = ""

g = Graph(state_schema=AgentState)

@g.node()
async def process_message(message: str, state: dict):
    print(f"Server processing: {message}")
    await asyncio.sleep(1) # simulate work
    state["reply"] = f"Echo: {message}"
    return state["reply"]

g.entrypoint = process_message

# To run this script:
# Option 1: pip install "flowk[api]"
# Option 2: pip install fastapi uvicorn
# 
# Then run: python api_example.py
if __name__ == "__main__":
    # This single line spins up a production-ready Web API!
    # - POST /invoke
    # - POST /stream
    # - GET /docs (Swagger UI)
    g.serve(port=8080)
