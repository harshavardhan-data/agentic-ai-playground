import pandas as pd
from core.sqlite_memory import SqliteSessionStore,MemoryTurn


DB_PATH = "sqlite:///./agent_memory.db"
STORAGE_DIR = "./storage"

def run_test():
    session_id = "test-session-persistence-123"

    print("=== PHASE 1: Initial Upload & Session Creation ===")
    store_before_restart = SqliteSessionStore(db_url=DB_PATH, storage_dir=STORAGE_DIR)

    # 1. Simulate a CSV upload
    dummy_df = pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "salary": [70000, 80000, 90000]
    })
    store_before_restart.update_sandbox_state(session_id, "df", dummy_df)
    
    # 2. Add a conversation turn to history
    turn = MemoryTurn(
        user_query="What is the average salary?",
        successful_code="df['salary'].mean()",
        execution_output="80000.0",
        summary="The average salary is 80,000."
    )
    store_before_restart.add_turn(session_id, turn)
    print("✓ Session created, CSV persisted to disk, turn recorded in SQLite.")

    # =========================================================================
    print("\n=== PHASE 2: Simulating Server Restart / Process Kill ===")
    # Explicitly delete the store instance from memory
    del store_before_restart
    print("✓ In-memory store instance destroyed. Server 'restarted'.")

    # =========================================================================
    print("\n=== PHASE 3: Recovery After Restart ===")
    # Instantiate a brand new store instance (mimics server bootup)
    store_after_restart = SqliteSessionStore(db_url=DB_PATH, storage_dir=STORAGE_DIR)

    # Retrieve the OLD session_id without re-uploading anything
    session = store_after_restart.get_session(session_id)

    # Assertions
    assert "df" in session.sandbox_state, "FAIL: DataFrame was not re-hydrated!"
    restored_df = session.sandbox_state["df"]
    
    assert len(restored_df) == 3, f"FAIL: Expected 3 rows, got {len(restored_df)}"
    assert len(session.history) == 1, f"FAIL: Expected 1 turn, got {len(session.history)}"
    assert session.history[0].user_query == "What is the average salary?", "FAIL: Query history mismatch"

    print("✓ SUCCESS: Session retrieved successfully!")
    print(f"  - Session ID: {session.session_id}")
    print(f"  - Restored Rows: {len(restored_df)}")
    print(f"  - Restored History Turns: {len(session.history)}")
    print(f"  - Restored Query: '{session.history[0].user_query}'")

if __name__ == "__main__":
    run_test()

    
    