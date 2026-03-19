import asyncio
from flowk import Graph  # pyre-ignore
from flowk.plugins.llm import OpenAIPlugin  # pyre-ignore
from flowk.metrics import MetricsRegistry  # pyre-ignore

# 1. Define the Sub-Graph (Research Agent)
research_graph = Graph()

@research_graph.node()
async def search_web(query: str):
    print(f"🔍 Searching web for: {query}")
    await asyncio.sleep(0.5)
    return f"Information about {query}: Flowk is awesome."

@research_graph.node()
async def summarize_info(info: str):
    return f"Summary: {info}"

research_graph.connect(search_web, summarize_info)

# 2. Define the Main Graph (Editor Agent)
main_graph = Graph()

# Register OpenAI plugin to track simulated costs
main_graph.checkpoint_db = "flowk_test.db"

@main_graph.node()
async def plan_outline(topic: str):
    return f"Outline for {topic}"

# Use the Research Graph as a Node!
research_node = research_graph.as_node(state_key="research_metadata")

@main_graph.node()
async def final_edit(research_summary: str, state: dict):
    print(f"📝 Final Edit based on: {research_summary}")
    print(f"📊 Internal Research State: {state.get('research_metadata')}")
    return f"Final Article using: {research_summary}"

main_graph.connect(plan_outline, research_node)
main_graph.connect(research_node, final_edit)

async def run():
    print("🚀 Running Multi-Agent Composite Graph...")
    result = await main_graph.arun("Future of AI Orchestration")
    print("-" * 30)
    print(f"RESULT: {result}")
    
    # Check metrics
    print("-" * 30)
    print("📈 METRICS SUMMARY:")
    # Normally we'd see usage here if we used the plugin with real output
    # For now, let's just use the CLI visualization
    main_graph.show()

if __name__ == "__main__":
    asyncio.run(run())
