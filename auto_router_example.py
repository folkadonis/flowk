import asyncio
from flowk import Graph  # pyre-ignore

g = Graph()

@g.node()
def parse_input(input_text: str, state: dict):
    state["user_query"] = input_text
    print(f"User asking: {input_text}")
    return input_text

@g.node()
def math_agent(state: dict):
    print("👨‍🔬 Math Agent selected. (Imagine doing calculations here...)")
    state["output"] = "100 (Calculated by Math Agent)"

@g.node()
def search_agent(state: dict):
    print("🔍 Search Agent selected. (Imagine searching Google here...)")
    state["output"] = "Latest news on the topic. (Found by Search Agent)"

@g.node()
def chat_agent(state: dict):
    print("🤖 Chat Agent selected. (Imagine generic chit-chat...)")
    state["output"] = "Hello to you too! (Answered by Chat Agent)"

# Connect Entrypoint
g.entrypoint = parse_input

# The Magic: Zero-Boilerplate LLM Routing!
# Instead of writing complex IF logic, we let GPT-4o-mini route automatically
@g.llm_router(
    model="gpt-4o-mini",
    targets={
        "math_agent": "Use this if the query contains numbers or mathematical equations.",
        "search_agent": "Use this if the user asks for real-time facts, current events, or news.",
        "chat_agent": "Use this for generic greetings, jokes, or chit-chat."
    }
)
def supervisor_router(state: dict):
    # Simply return the context we want the LLM to base its decision on
    return state.get("user_query", "")

# Connect the node to the router
g.connect(parse_input, supervisor_router)

# Ensure OPENAI_API_KEY is exported in your terminal before running this!
if __name__ == "__main__":
    import os
    if "OPENAI_API_KEY" not in os.environ:
        print("Please export OPENAI_API_KEY to test the LLM Router.")
        
    async def run_demos():
        print("\n--- Demo 1: Math Query ---")
        await g.arun(input_data="What is 55 times 102?", session_id="demo_1")
        
        print("\n--- Demo 2: News Query ---")
        await g.arun(input_data="Who won the superbowl yesterday?", session_id="demo_2")
        
        print("\n--- Demo 3: Chit Chat ---")
        await g.arun(input_data="Hey bot, what's up?", session_id="demo_3")

    asyncio.run(run_demos())
