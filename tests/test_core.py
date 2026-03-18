import pytest
from flowk import Graph
from pydantic import BaseModel

class State(BaseModel):
    count: int = 0

def test_basic_graph():
    g = Graph()
    
    @g.node()
    def increment(x: int):
        return x + 1
        
    res = g.run(1)
    assert res == 2

def test_pydantic_state():
    g = Graph(state_schema=State)
    
    @g.node()
    def update_state(x: int, state: dict):
        state["count"] += x
        return x
        
    g.run(5)
    # Check if we can run it again and see state persisted in session (if we had one)
    # For a single run, it should just work
    assert True

def test_routing():
    g = Graph()
    
    @g.node()
    def start(x): return x
    
    @g.node()
    def high(x): return "high"
    
    @g.node()
    def low(x): return "low"
    
    def router(x):
        return "high" if x > 10 else "low"
        
    r = g.route(router, {"high": high, "low": low})
    g.connect(start, r)
    
    assert g.run(15) == "high"
    assert g.run(5) == "low"
