import ast
import io
import re
from contextlib import redirect_stdout
from typing import Any, Dict, Tuple

class SecurityException(Exception):
    """Custom exception for AST security violations."""
    pass

class CodeSandbox:
    BANNED_IMPORTS = {"os", "sys", "subprocess", "shutil", "requests", "socket"}
    BANNED_FUNCTIONS = {"eval", "exec", "open", "compile"}

    @staticmethod
    def clean_code(raw_code: str) -> str:
        cleaned = re.sub(r"```python\s*", "", raw_code)
        return re.sub(r"```\s*$", "", cleaned).strip()

    @classmethod
    def verify_safety(cls, code_str: str) -> None:
        try:
            tree = ast.parse(code_str)
        except SyntaxError:
            return  # Let Python handle syntax errors natively during execution

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in cls.BANNED_IMPORTS:
                        raise SecurityException(f"Banned library '{alias.name}' detected.")
            
            elif isinstance(node,ast.ImportFrom):
                if node.module in cls.BANNED_IMPORTS:
                    raise PermissionError(f"Security Block: Banned library '{node.module}' detected.")
            
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in cls.BANNED_FUNCTIONS:
                    raise SecurityException(f"Banned function '{node.func.id}()' detected.")

    @classmethod
    def execute(cls, code: str, global_vars: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Returns (Success_Bool, Output_or_Error_String)
        """
        sanitized = cls.clean_code(code)
        
        try:
            cls.verify_safety(sanitized)
        except SecurityException as e:
            return False, str(e)

        output_buffer = io.StringIO()
        try:
            with redirect_stdout(output_buffer):
                exec(sanitized, global_vars)
            return True, output_buffer.getvalue().strip()
        except Exception as e:
            import traceback
            return False, traceback.format_exc()