import re

def clean_generated_code(raw_code:str) -> str:
    """Strips markdown code fences and unnecessary spacing from the generated string."""
    # Remove markdown code blocks if present
    cleaned=re.sub(r"```python\s*","",raw_code)
    cleaned=re.sub(r"```\s*$","",cleaned)
    return cleaned.strip()

## AST Sandbox(Static Code Guard) ,stopping code if it imports risky libraries

import ast

def verify_code_safety(code_str: str) -> bool:
    """Statically analyzes the code structure to block unsafe imports or function calls."""
    try:
        tree=ast.parse(code_str)
    except SyntaxError:
        # If it's a syntax error, let our Day 3 loop handle it naturally via runtime error traces
        return True
    
    # Banned operations list
    BANNED_IMPORTS={"os","sys","subprocess","shutil","requests","socket"}
    BANNED_FUNCTIONS={"eval","exec","open","compile"}

    for node in ast.walk(tree):
        # Check for direct imports (e.g, import os)
        if isinstance(node,ast.Import):
            for alias in node.names:
                if alias.name in BANNED_IMPORTS:
                    raise PermissionError(f"Security Block: Banned library '{node.module}' detected.") 
        # Check for from-imports (e.g., from os import path)
        elif isinstance(node,ast.ImportFrom):
            if node.module in BANNED_IMPORTS:
                raise PermissionError(f"Security Block: Banned library '{node.module}' detected.")
            
        # Check for unsafe function execution calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_FUNCTIONS:
                raise PermissionError(f"Security Block: Banned function call '{node.func.id}()' detected.")
        
    return True


if __name__ == "__main__":
    pass