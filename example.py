import time
import json
from pydantic import BaseModel, Field
from flowk import Graph

# 1. Define a strict State Schema using Pydantic
class GraphSchema(BaseModel):
    category: str = "general"
    history: list[str] = Field(default_factory=list)
    original_text: str = ""

# 2. Initialize Graph with Schema and SQLite Persistence
g = Graph(state_schema=GraphSchema, checkpoint_db="flowk_memory.db")

@g.node(retries=2)
def parse_input(text: str, state: dict):
    # This automatically tracks history across execution runs!
    state["history"].append(text)
    state["original_text"] = text
    return text.strip().lower()

@g.node()
def categorize(text: str, state: dict):
    if "urgent" in text:
        state["category"] = "priority"
    else:
        state["category"] = "standard"
    return text

def router(category: str):
    # Route logic based on passing output from categorizer
    return "analyze"

@g.node()
def process_priority(text: str):
    time.sleep(0.1) # Simulate work
    return f"[PRIORITY PROCESSED] {text.upper()}"

@g.node()
def process_standard(text: str):
    time.sleep(0.1) # Simulate work
    return f"[STANDARD PROCESSED] {text.capitalize()}"

@g.node()
def summarize(text: str, state: dict):
    return {
        "final": text,
        "metadata": state.to_dict()
    }

# Build connections
g.connect(parse_input, categorize)

# Routing condition mapping
# Categorize -> Routing Branch -> Summarize
r_node = g.route(router, {
    "priority": process_priority,
    "standard": process_standard,
    "analyze": process_priority   # Fallback mapping
})

g.connect(categorize, r_node)
g.connect(process_priority, summarize)
g.connect(process_standard, summarize)

if __name__ == "__main__":
    print("=== RUNNING BASIC ===")
    res = g.run("  This is an URGENT request!  ")
    print("Result:", res)
    
    print("\n=== RUNNING MULTI-TURN MEMORY SESSION ===")
    r1 = g.run("Hello", session_id="user_john")
    print("Turn 1 History:", r1["metadata"]["history"])
    
    r2 = g.run("Are you there?", session_id="user_john")
    print("Turn 2 History:", r2["metadata"]["history"])
    
    from flowk.metrics import MetricsRegistry
    import json
    print("\n=== METRICS ===")
    print(json.dumps(MetricsRegistry.get_summary(), indent=2))
    
    print("\n=== VISUALIZATION ===")
    g.show()
