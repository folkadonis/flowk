import pytest
from flowk import Graph  # type: ignore  # pyre-ignore
from pydantic import BaseModel  # type: ignore  # pyre-ignore
from flowk.memory import MemoryStore  # type: ignore  # pyre-ignore


# Reset memory store between tests to prevent state leaking
@pytest.fixture(autouse=True)
def reset_memory():
    MemoryStore.reset()
    yield
    MemoryStore.reset()


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
        state["count"] = state.get("count", 0) + x
        return x

    result = g.run(5)
    assert result == 5  # node returns input, state mutation is side-effect


def test_routing():
    g = Graph()

    @g.node()
    def start(x):
        return x

    @g.node()
    def high(x):
        return "high"

    @g.node()
    def low(x):
        return "low"

    def router(x):
        return "high" if x > 10 else "low"

    r = g.route(router, {"high": high, "low": low})
    g.connect(start, r)
    g.compile()

    assert g.run(15) == "high"
    assert g.run(5) == "low"


def test_session_memory():
    """Verify that state persists across runs on the same session."""
    g = Graph()

    @g.node()
    def counter(x: int, state: dict):
        state["count"] = state.get("count", 0) + 1
        return state["count"]

    run1 = g.run(0, session_id="test-session")
    run2 = g.run(0, session_id="test-session")

    assert run1 == 1
    assert run2 == 2  # state carried over from first run
