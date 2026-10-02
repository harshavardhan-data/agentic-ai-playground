import ast
import io
import re
import pickle
import traceback
import contextlib
import time
import multiprocessing as mp
from typing import Any, Dict, Tuple
import pandas as pd
from models.execution_results import PythonExecutionResult

class SecurityException(Exception):
    """Custom exception for AST security violations."""
    pass


def _worker(code: str, state_bytes: bytes, result_queue: mp.Queue) -> None:
    """
    Runs INSIDE the child process. Completely separate memory space
    from your main app.
    """
    start_time=time.perf_counter()
    state = pickle.loads(state_bytes)
    output_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(code, state)

        # Only keep picklable, "data-like" values before sending state back.
        # Modules/functions the code may have imported aren't picklable
        # and aren't state we care about persisting anyway.
        clean_state = {}
        for k, v in state.items():
            if k == "__builtins__":
                continue
            try:
                pickle.dumps(v)
                clean_state[k] = v
            except Exception as e:
                continue

        execution_time_ms = (time.perf_counter() - start_time) * 1000
        result_queue.put(("success", output_buffer.getvalue(), pickle.dumps(clean_state),execution_time_ms))
    except Exception:
        execution_time_ms = (time.perf_counter() - start_time) * 1000
        result_queue.put(("error", traceback.format_exc(), None,execution_time_ms))

class CodeSandbox:
    BANNED_IMPORTS = {"os", "sys", "subprocess", "shutil", "requests", "socket","pathlib"}
    BANNED_FUNCTIONS = {"eval", "exec", "open", "compile","__import__"}

    @staticmethod
    def clean_code(raw_code: str) -> str:
        cleaned = re.sub(r"```python\s*", "", raw_code)
        return re.sub(r"```\s*$", "", cleaned).strip()

    @classmethod
    def verify_safety(cls, code_str: str) -> None:
        try:
            tree = ast.parse(code_str)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in cls.BANNED_IMPORTS:
                        raise SecurityException(f"Banned library '{alias.name}' detected.")
            elif isinstance(node, ast.ImportFrom):
                if node.module in cls.BANNED_IMPORTS:
                    raise SecurityException(f"Banned library '{node.module}' detected.")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in cls.BANNED_FUNCTIONS:
                    raise SecurityException(f"Banned function '{node.func.id}()' detected.")


    @staticmethod
    def build_schema_string(df: pd.DataFrame) -> str:
        """Same idea as your hand-written mock_schema in __main__, generated for real."""
        # Capture structural details
        columns_and_types=df.dtypes.to_dict()
        missing_values=df.isnull().sum()

        schema_summary = "Dataset Schema Information:\n"

        for col, dtype in columns_and_types.items():
            schema_summary += f"- Column: {col} | Type: {dtype}"

            if missing_values[col] > 0:
                schema_summary += f" | Missing Values: {missing_values[col]}"

            schema_summary += "\n"

        return schema_summary

    @classmethod
    def execute(cls, code: str, global_vars: Dict[str, Any], timeout: int = 10) -> Tuple[bool, str]:
        """
        Returns (Success_Bool, Output_or_Error_String).
        Runs the code in an isolated subprocess with a hard timeout.
        On success, global_vars is updated in place (same contract as before).
        """

        sanitized = cls.clean_code(code)

        try:
            cls.verify_safety(sanitized)
        except SecurityException as e:
            return PythonExecutionResult.failure(error_message=f"Security Issue :{str(e)} ")

        try:
            state_bytes = pickle.dumps(global_vars)
        except Exception as e:
            return PythonExecutionResult.failure(error_message=f"Possible Serialization Issue : {str(e)}")

        result_queue: mp.Queue = mp.Queue()
        proc = mp.Process(target=_worker, args=(sanitized, state_bytes, result_queue))
        proc.start()
        proc.join(timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join()
            return PythonExecutionResult.failure(error_message=f"Execution timed out after {timeout} seconds (possible infinite loop).",
                                                 execution_time_ms=timeout*1000,)

        if result_queue.empty():
            return PythonExecutionResult.failure(error_message="Process exited without returning a result (it may have crashed unexpectedly).",
                                                 execution_time_ms=timeout*1000,)

        status, payload, new_state_bytes ,execution_time_ms = result_queue.get()

        if status == "error":
            return PythonExecutionResult.failure(error_message=payload, execution_time_ms=execution_time_ms)

        # Success: merge the updated state back in, same as your old in-place mutation
        new_state = pickle.loads(new_state_bytes)
        global_vars.update(new_state)
        return PythonExecutionResult.ok(result=payload.strip(), execution_time_ms=execution_time_ms)