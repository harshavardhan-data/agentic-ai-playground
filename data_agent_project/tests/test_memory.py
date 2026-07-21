import pytest
from core.memory import InMemorySessionStore,MemoryTurn

def test_memory_fifo_eviction_boundary():
    # Arrange: Setup a memory manager capped at 2 entries
    mgr=InMemorySessionStore(max_turns=2)
    session_id="user_123"

    turn1 = MemoryTurn(user_query="Q1", successful_code="C1", execution_output="O1")
    turn2 = MemoryTurn(user_query="Q2", successful_code="C2", execution_output="O2")
    turn3 = MemoryTurn(user_query="Q3", successful_code="C3", execution_output="O3")

    # Act
    mgr.add_turn(session_id, turn1)
    mgr.add_turn(session_id, turn2)
    assert len(mgr.get_session(session_id).history) == 2
    
    mgr.add_turn(session_id, turn3)
    history = mgr.get_session(session_id).history

    # Assert: Verify total capacity is maintained and the oldest item (turn1) was evicted
    assert len(history) == 2
    assert history[0].user_query == "Q2"
    assert history[1].user_query == "Q3"


def test_memory_session_isolation():
    mgr = InMemorySessionStore()
    turn = MemoryTurn(user_query="Q1", successful_code="C1", execution_output="O1")
    
    mgr.add_turn("user_A", turn)
    
    # Assert: Data must be inaccessible across different session boundaries
    assert len(mgr.get_session("user_B").history) == 0