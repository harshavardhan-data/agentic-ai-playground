import re
import sqlite3
import traceback
import multiprocessing as mp
from typing import Tuple
import pandas as pd
from core.logger import get_logger
from models.execution_results import SqlExecutionResult
from models.db_context import DatabaseContext
import time


logger=get_logger(__name__)

class SqlSecurityException(Exception):
    pass


def _worker(query:str,db_path:str,auto_limited:bool,max_rows:int,result_queue:mp.Queue) -> None:
    """Runs in an isolated subprocess. Opens its own connection — never
    shares one across threads or processes."""
    start = time.perf_counter()
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            df = pd.read_sql_query(query, conn)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        if len(df) > max_rows:
            df = df.head(max_rows)

        
        result_queue.put(SqlExecutionResult.ok(result_df=df,execution_time_ms=elapsed_ms))
        logger.info("Sql Query Execution Succesful",extra={"extra_data":{"time_elapsed":elapsed_ms,"rows_returned":len(df),}},)
    except sqlite3.Error as e:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.error(f"Sql Error: {str(e)}")
        result_queue.put(SqlExecutionResult.failure(error_message=str(e),execution_time_ms=elapsed_ms))
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception("Unexpected SQL Error, sandbox failure", extra={"extra_data": {"traceback": traceback.format_exc()}})
        result_queue.put(SqlExecutionResult.failure(error_message=str(e),execution_time_ms=elapsed_ms))


class SqlSandbox:
    BANNED_KEYWORDS = {
        "insert", "update", "delete", "drop", "alter",
        "create", "attach", "detach", "pragma", "vacuum", "replace"
    }


    @staticmethod
    def normalize_query(query:str) -> str:
        return query.strip().rstrip(";").strip()

    @staticmethod
    def inject_limit(query:str,max_rows:int):
        """
        Inject LIMIT if one is not already present.

        Returns:
            (modified_query, auto_limited)
        """
        if re.search(r"\blimit\b", query, re.IGNORECASE):
            return query, False

        return f"{query} LIMIT {max_rows}", True

    @classmethod
    def verify_safety(cls, query: str) -> None:
        normalized = cls.normalize_query(query).lower()
        if not (normalized.startswith("select") or normalized.startswith("with")):
            raise SqlSecurityException("Only SELECT statements (including WITH/CTE) are permitted.")
        for word in cls.BANNED_KEYWORDS:
            if re.search(rf"\b{word}\b", normalized):
                raise SqlSecurityException(f"Banned keyword '{word}' detected.")

    @classmethod
    def get_schema(cls, db_path: str) -> str:

        conn=sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
            names = [row[0] for row in cursor.fetchall()]
            lines = []
            for name in names:
                cursor.execute(f'PRAGMA table_info("{name}")')
                cols = [f"{col[1]} ({col[2]} {',NULLABLE' if col[3]==0 else ''})" for col in cursor.fetchall()]
                lines.append(f"{name}: " + ", ".join(cols))
            
            return "\n".join(lines)
        finally:
            conn.close()
    @classmethod
    def get_database_context(cls, db_path: str, max_rows: int = 500) -> DatabaseContext:
        conn=sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
            views = [row[0] for row in cursor.fetchall()]
            cursor.execute("SELECT name FROM sqlite_temp_master WHERE type='table'")
            temp_tables = [row[0] for row in cursor.fetchall()]
        
            return DatabaseContext(
                dialect="SQLite", database_name=db_path.split("/")[-1],
                execution_mode="Read Only", views=views,
                temporary_tables=temp_tables, max_rows=max_rows
            )
        finally:
            conn.close()
    
    @classmethod
    def execute(cls, query: str, db_path: str, max_rows: int = 500, timeout: int = 5) -> SqlExecutionResult:
        cleaned = cls.normalize_query(query)
        try:
            cls.verify_safety(query)
        except SqlSecurityException as e:
            return SqlExecutionResult.failure(error_message="Security Issue")

        # Inject LIMIT at the SQL level, not just after fetching — this stops the
        # database engine from doing unnecessary work in the first place, rather
        # than pulling everything into memory and discarding rows in Python.
        cleaned,auto_limited=cls.inject_limit(cleaned,max_rows)

        result_queue: mp.Queue = mp.Queue()
        proc = mp.Process(target=_worker, args=(cleaned, db_path,auto_limited, max_rows, result_queue))
        proc.start()
        proc.join(timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join()
            return SqlExecutionResult.failure(f"Query timed out after {timeout} seconds. (Possible infinite loop.)",execution_time_ms=timeout*1000)

        if result_queue.empty():
            return SqlExecutionResult.failure(error_message="Process exited without any result",execution_time_ms=timeout*1000)

        result:SqlExecutionResult = result_queue.get()
      
        return result
