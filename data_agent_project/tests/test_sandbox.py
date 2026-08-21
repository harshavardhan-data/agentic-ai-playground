import time
import pytest
from sandboxes.code_sandbox import CodeSandbox, SecurityException


# ---------------------------------------------------------
# Test 1: Normal, correct code should succeed and print output
# ---------------------------------------------------------

def test_sandbox_happy_path():
    # Arrange
    code = "result = x + y\nprint(result)"
    state = {"x": 10, "y": 20}
    
    # Act
    success, output = CodeSandbox.execute(code, state)
    
    # Assert
    assert success is True
    assert output == "30"
    assert state["result"] == 30 # Proves memory state was modified


# ---------------------------------------------------------
# Test 2: State should persist and come back updated
# (this is the thing pickling could have silently broken)
# ---------------------------------------------------------
def test_state_persists_across_execution():
    state = {"df_length": 4}
    code = "df_length = df_length * 2\nprint(df_length)"

    success, output = CodeSandbox.execute(code, state)

    assert success is True
    assert output == "8"
    # the KEY check: did the subprocess's changes make it back into
    # our original dict? If pickling/merging is broken, this fails
    # even though `success` was True and output looked right.
    assert state["df_length"] == 8


# ---------------------------------------------------------
# Test 3: A real runtime crash should be caught, not raised
# ---------------------------------------------------------

def test_sandbox_runtime_error():
    # Arrange
    broken_code = "print(10 / 0)"
    state={}
    
    # Act
    success, output = CodeSandbox.execute(broken_code, state)
    
    # Assert
    assert success is False
    assert "ZeroDivisionError" in output

# ---------------------------------------------------------
# Test 4: Banned imports should be rejected before execution
# (this is the AST denylist check, still relevant)
# ---------------------------------------------------------
def test_banned_import_is_blocked():
    malicious_code = "import os\nprint(os.getcwd())"
    state = {}

    success, output = CodeSandbox.execute(malicious_code, state)

    assert success is False
    assert "Banned library" in output

# ---------------------------------------------------------
# Test 5: THE important one — infinite loop must be KILLED,
# not left to hang forever
# ---------------------------------------------------------
def test_infinite_loop_times_out():
    code = "while True:\n    pass"
    state = {}

    start = time.time()
    success, output = CodeSandbox.execute(code, state, timeout=3)
    elapsed = time.time() - start

    assert success is False
    assert "timed out" in output.lower()
    # confirms it didn't actually run forever - should return
    # shortly after the timeout, not hang the test suite
    assert elapsed < 5