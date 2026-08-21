import pytest
import os
import sqlite3
import time
import tempfile
from sandboxes.sql_sandbox import SqlSandbox

@pytest.fixture
def sample_db():

    fd,path=tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn=sqlite3.connect(path)
    conn.execute("CREATE TABLE products (id INTEGER,name TEXT,price REAL)")
    conn.execute("INSERT INTO products VALUES(1,'Widget',9.99)")
    conn.execute("INSERT INTO products VALUES(2,'Gadget',22.09)") 
    conn.commit()
    conn.close()

    yield path
    os.remove(path)

def test_successful_select(sample_db):
    result=SqlSandbox.execute("SELECT name,price FROM products WHERE id=1",sample_db)
    assert result.success is True
    assert result.result_df.iloc[0]["name"]=="Widget"
    assert result.rows_returned == 1
    assert result.execution_time_ms >= 0
    assert result.error_message is None

def test_with_cte_allowed(sample_db):
    query = "WITH cheap AS (SELECT * FROM products WHERE price < 15) SELECT name FROM cheap"
    result=SqlSandbox.execute(query,sample_db)
    assert result.success is True
    assert result.result_df.iloc[0]["name"]=="Widget"
    assert result.rows_returned == 1

def test_drop_blocked(sample_db):
    result = SqlSandbox.execute("DROP TABLE products", sample_db)
    assert result.success is False
    assert "Issue" in result.error_message 

def test_insert_blocked(sample_db):
    result = SqlSandbox.execute("INSERT INTO products VALUES (3, 'Hack', 0)", sample_db)
    assert result.success is False
    assert "Issue" in result.error_message


def test_invalid_column_caught(sample_db):
    result = SqlSandbox.execute("SELECT nonexistent_col FROM products", sample_db)
    assert result.success is False
    # assert "sql error" in result.error_message.lower()
    assert result.result_df is None
    assert result.rows_returned is None


# def test_auto_limit_applied(sample_db):
#     success, output = SqlSandbox.execute("SELECT * FROM products", sample_db, max_rows=1)
#     assert success is True
#     assert "limit 1 applied automatically" in output.lower()


def test_runaway_query_times_out(sample_db):
    slow_query = """
    WITH RECURSIVE counter(x) AS (
        SELECT 1 UNION ALL SELECT x+1 FROM counter WHERE x < 100000000
    )
    SELECT count(*) FROM counter
    """
    start = time.time()
    result = SqlSandbox.execute(slow_query, sample_db, timeout=2)
    elapsed = time.time() - start
    assert result.success is False
    assert result.result_df is None
    assert "query timed out" in result.error_message.lower()
    assert elapsed < 4


# def test_oversized_user_limit_still_capped(sample_db):
#     # Query supplies its OWN limit, larger than max_rows.
#     # Must still be capped — this is the backstop, not the auto-inject path.
#     result = SqlSandbox.execute(
#         "SELECT * FROM products LIMIT 100000", sample_db, max_rows=1
#     )
#     assert result.success is True
#     assert "truncated to first 1" in output.lower()