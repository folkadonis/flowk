import sys
import traceback
sys.path.insert(0, r'c:\Users\Folk Nallathambi\Documents\flowk')

from flowk import Graph  # type: ignore
from flowk.memory import MemoryStore  # type: ignore

def run_test(name, fn):
    try:
        fn()
        print(f"PASS: {name}")
    except Exception as e:
        print(f"FAIL: {name}")
        traceback.print_exc()

def test_basic_graph():
    MemoryStore.reset()
    g = Graph()
    @g.node()
    def increment(x):
        return x + 1
    res = g.run(1)
    assert res == 2, f"Expected 2, got {res}"

def test_routing():
    MemoryStore.reset()
    g = Graph()
    @g.node()
    def start(x): return x
    @g.node()
    def high(x): return "high"
    @g.node()
    def low(x): return "low"
    def router(x): return "high" if x > 10 else "low"
    r = g.route(router, {"high": high, "low": low})
    g.connect(start, r)
    g.compile()
    r1 = g.run(15)
    r2 = g.run(5)
    assert r1 == "high", f"Expected 'high', got {r1!r}"
    assert r2 == "low",  f"Expected 'low', got {r2!r}"

def test_session_memory():
    MemoryStore.reset()
    g = Graph()
    @g.node()
    def counter(x, state: dict):
        state["count"] = state.get("count", 0) + 1
        return state["count"]
    r1 = g.run(0, session_id="ts")
    r2 = g.run(0, session_id="ts")
    assert r1 == 1, f"run1 expected 1, got {r1}"
    assert r2 == 2, f"run2 expected 2, got {r2}"

run_test("test_basic_graph", test_basic_graph)
run_test("test_routing", test_routing)
run_test("test_session_memory", test_session_memory)
print("Done.")
