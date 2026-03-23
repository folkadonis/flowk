from pydantic import BaseModel, ConfigDict
from flowk import Graph, GraphState
from flowk.plugins import PluginManager, LoggerPlugin
import time

# 1. Attach the global LoggerPlugin we just built!
PluginManager.register(LoggerPlugin())

# 2. Define standard typed State
class MyStateSchema(BaseModel):
    model_config = ConfigDict(extra='allow')
    subject: str = ""
    email_body: str = ""
    quality: int = 0
    needs_retry: bool = False

# 3. Instantiate the powerful v2 Graph Engine
g = Graph(state_schema=MyStateSchema)

# 4. Define Nodes
@g.node()
def write_email(input_data: str, state: dict):
    state["subject"] = input_data
    state["email_body"] = f"Hello! Here is the content about {input_data}."
    return "email_written"

@g.node()
def evaluate_email(input_data: str, state: dict):
    # Simulate a quality check
    if len(state["subject"]) > 5:
        state["quality"] = 90
        state["needs_retry"] = False
        return "pass"
    else:
        state["quality"] = 40
        state["needs_retry"] = True
        return "fail"

@g.node()
def rewrite_email(input_data: str, state: dict):
    state["subject"] = state["subject"] + " (Improved)"
    state["email_body"] += " We have made this even better."
    return "email_written"

@g.node()
def persist_email(input_data: str, state: dict):
    print(f"\n📧 FINAL EMAIL SAVED: {state['subject']}\n")
    return "done"

# 5. Define Connections & Routing (DAG Engine)
g.connect(write_email, evaluate_email)

# Conditional LLM-like Router
g.route(
    condition_fn=lambda _: evaluate_email, 
    mapping_dict={
        "pass": persist_email,
        "fail": rewrite_email
    }
)
g.connect(rewrite_email, evaluate_email) # Loop back!

# 6. Execute Flowk v2 natively
if __name__ == "__main__":
    print("\n🚀 STARTING FLOWK V2 ENGINE 🚀\n")
    # Will trigger the 'fail' condition first because 'Hi' is short!
    g.run("Hi") 
    print("\n✅ WORKFLOW COMPLETE!\n")
