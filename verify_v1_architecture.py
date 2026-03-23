import asyncio
import time
from flowk import Graph
from flowk.node import Node
from flowk.storage import StorageRegistry
from flowk.memory import MemoryStore

async def test_v1_core():
    # 1. Setup
    db = "v1_test.db"
    g = Graph(checkpoint_db=db)
    
    @g.node()
    def start_node(input_data, state):
        state["started"] = True
        time.sleep(0.1)
        return "step_1"

    @g.node()
    def end_node(input_data, state):
        state["finished"] = True
        return "done"

    g.connect(start_node, end_node)
    g.compile()

    print("🚀 Running Async Execution...")
    run_id = "test_run_v1"
    result = await g.arun(input_data="hello", run_id=run_id)
    
    # 2. Verify Event Sourcing
    print("📋 Verifying Event Log...")
    events = StorageRegistry.get_events(run_id)
    
    event_types = [e["type"] for e in events]
    print(f"Events found: {event_types}")
    
    assert "run_start" in event_types
    assert "node_start" in event_types
    assert "node_end" in event_types
    assert "run_end" in event_types
    
    # Check data in events
    start_event = next(e for e in events if e["type"] == "run_start")
    assert start_event["data"]["input"] == "hello"
    
    end_node_event = next(e for e in events if e["node"] == "end_node" and e["type"] == "node_end")
    assert end_node_event["data"]["state"]["finished"] is True
    
    print("✅ Event Sourcing Verified!")

    # 3. Verify Persistence
    trace = StorageRegistry.get_trace(run_id)
    assert len(trace) == 2
    print("✅ Persistence Verified!")

if __name__ == "__main__":
    asyncio.run(test_v1_core())
