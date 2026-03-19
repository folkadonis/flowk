import asyncio
from flowk import Graph
from flowk.memory import MemoryStore

async def populate():
    print("Initializing Flowk graph with checkpointing enabled...")
    
    # Connect graph to the default dashboard database!
    g = Graph(checkpoint_db="flowk_memory.db")
    
    @g.node()
    async def ingest_data(data: str, state: dict):
        state["raw_data"] = data
        state["tokens"] = len(data.split())
        return f"Ingested {state['tokens']} tokens"
        
    @g.node()
    async def process_data(status: str, state: dict):
        state["processed"] = True
        state["status"] = "SUCCESS"
        return "Processing complete"
        
    g.connect(ingest_data, process_data)
    g.compile()
    
    print("Running Session 1: Alpha-Core...")
    await g.arun("Flowk is an autonomous AI agent framework", session_id="session-alpha-core")
    
    print("Running Session 2: Beta-Analytics...")
    await g.arun("Observability is key to production readiness.", session_id="session-beta-analytics")
    
    print("Running Session 3: Gamma-Stream...")
    await g.arun("Streaming events via Server-Sent Events is awesome.", session_id="session-gamma-stream")
    
    print("\n✅ Successfully populated flowk_memory.db with 3 rich execution sessions!")
    print("👉 Refresh your Streamlit Dashboard (localhost:8501) to view them.")

if __name__ == "__main__":
    asyncio.run(populate())
