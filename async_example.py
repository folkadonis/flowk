import asyncio
from pydantic import BaseModel, ConfigDict
from flowk import Graph

# 1. Type-Safe State
class Schema(BaseModel):
    model_config = ConfigDict(extra="allow")
    message: str = ""
    approved: bool = False

g = Graph(state_schema=Schema)

@g.node()
async def prepare(text: str, state: dict):
    # Demonstrating async yielding/sleep
    await asyncio.sleep(0.1)
    state["message"] = text
    return text

@g.node()
async def parallel_task_a(text: str):
    await asyncio.sleep(0.5)
    return "Task A Done"

@g.node()
async def parallel_task_b(text: str):
    await asyncio.sleep(0.3)
    return "Task B Done"

@g.node()
def human_review(text: str, state: dict):
    # We will interrupt execution BEFORE this node runs.
    # When resumed, we will check if human approved.
    if state.get("approved"):
        return "Approved!"
    return "Rejected!"

@g.node()
def final_node(text: str):
    return f"FINAL: {text}"

# Graph Construction
g.connect(prepare, parallel_task_a)
g.connect(prepare, parallel_task_b)

# Both parallel tasks flow into human_review naturally
g.connect(parallel_task_a, human_review)
g.connect(parallel_task_b, human_review)

g.connect(human_review, final_node)

# 2. Compile with an interrupt breakpoint
g.compile(interrupt_before=["human_review"])


async def main():
    print("=== STREAMING ASYNC EXECUTION ===")
    session = "v2_test_sess"
    
    async for event in g.astream("Start Pipeline", session_id=session):
        e_type = event["type"]
        if e_type == "node_end":
            print(f"✅ Node Finished: {event['node']} -> {event['output']}")
        elif e_type == "interrupt":
            print(f"⏸️ INTERRUPTED BEFORE: {event['nodes']}")
            
            # 3. Modify state via human interaction
            print(f"👤 Human is looking at state: {event['state']}")
            print("👤 Human approves...")
            # We persist the new state into memory
            from flowk.memory import MemoryStore
            state = event["state"]
            state["approved"] = True
            MemoryStore.save_state(session, state)
            
            # 4. Resume
            print("\n▶️ RESUMING PIPELINE...")
            
    # To run it until end after interrupt, we just call arun or astream again
    print("\n[Resuming from save point]")
    final_output = await g.arun(None, session_id=session)
    print("🏁 FINAL OUTPUT:", final_output)
    
    print("\n=== VISUALIZATION ===")
    g.show()

if __name__ == "__main__":
    asyncio.run(main())
