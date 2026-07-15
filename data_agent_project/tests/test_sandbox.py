import pytest
from tools.sandbox import CodeSandbox, SecurityException

def test_sandbox_happy_path():
    # Arrange
    code = "result = x + y\nprint(result)"
    globals_dict = {"x": 10, "y": 20}
    
    # Act
    success, output = CodeSandbox.execute(code, globals_dict)
    
    # Assert
    assert success is True
    assert output == "30"
    assert globals_dict["result"] == 30 # Proves memory state was modified

def test_sandbox_security_block():
    # Arrange
    malicious_code = "import os\nprint(os.getcwd())"
    
    # Act
    success, output = CodeSandbox.execute(malicious_code, {})
    
    # Assert
    assert success is False
    assert "Banned library 'os' detected" in output

def test_sandbox_runtime_error():
    # Arrange
    broken_code = "print(10 / 0)"
    
    # Act
    success, output = CodeSandbox.execute(broken_code, {})
    
    # Assert
    assert success is False
    assert "ZeroDivisionError" in output