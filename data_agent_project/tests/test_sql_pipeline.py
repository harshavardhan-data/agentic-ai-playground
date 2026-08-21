import os
import sqlite3
import tempfile
import pytest
from unittest.mock import MagicMock,patch

from models.llm_schemas import SqlResponse,SQLCriticVerdict
from core.memory import InMemorySessionStore
import sql_main


@pytest.fixture
def temp_db(tmp_path):

    fd,path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn=sqlite3.connect(path)
    conn.execute("CREATE TABLE products (id INTEGER, name TEXT, price REAL)")
    conn.execute("INSERT INTO products VALUES (1, 'Widget', 9.99)")
    conn.commit()
    conn.close()
    yield path
    os.remove(path)


def make_session(temp_db, session_id="s1"):
    memory = InMemorySessionStore()
    session = memory.get_session(session_id)
    session.sandbox_state["db_path"] = temp_db
    return memory, session

def fake_coder(sql_responses):
    fake=MagicMock()
    fake.generate_sql_query.side_effect=sql_responses
    return fake

def fake_critic(verdicts):
    fake=MagicMock()
    fake.evaluate_logic.side_effect=verdicts
    return fake

@patch("sql_main.SummarizerAgent")
@patch("sql_main.SqlCriticAgent")
@patch("sql_main.SqlCoderAgent")
def test_succeeds_first_try(mock_coder_cls, mock_critic_cls, mock_summarizer_cls, temp_db):
    memory, session = make_session(temp_db)

    mock_coder_cls.return_value = fake_coder([
        SqlResponse(info="fetch widget", sql_query="SELECT name FROM products WHERE id = 1")
    ])
    mock_critic_cls.return_value = fake_critic([
        SQLCriticVerdict(is_correct=True, critique="")
    ])
    mock_summarizer_cls.return_value.summarize.return_value = "fetched widget name"

    result = sql_main.run_sql_healing_pipeline(user_query="get widget name", session=session, memory=memory)

    assert result is not None
    assert "Widget" in result
    assert mock_coder_cls.return_value.generate_sql_query.call_count == 1


@patch("sql_main.SummarizerAgent")
@patch("sql_main.SqlCriticAgent")
@patch("sql_main.SqlCoderAgent")
def test_recovers_from_execution_error(mock_coder_cls, mock_critic_cls, mock_summarizer_cls, temp_db):
    memory, session = make_session(temp_db)

    mock_coder_cls.return_value = fake_coder([
        SqlResponse(info="bad column", sql_query="SELECT nonexistent_col FROM products"),  # real error via real SqlSandbox
        SqlResponse(info="fixed", sql_query="SELECT name FROM products WHERE id = 1")
    ])
    mock_critic_cls.return_value = fake_critic([
        SQLCriticVerdict(is_correct=True, critique="")   # only reached on the successful attempt
    ])
    mock_summarizer_cls.return_value.summarize.return_value = "summary"

    result = sql_main.run_sql_healing_pipeline(user_query="get widget name", session=session, memory=memory)

    assert result is not None
    assert "Widget" in result
    assert mock_coder_cls.return_value.generate_sql_query.call_count == 2
    assert mock_critic_cls.return_value.evaluate_logic.call_count == 1   # never saw the crashed attempt




@patch("sql_main.SummarizerAgent")
@patch("sql_main.SqlCriticAgent")
@patch("sql_main.SqlCoderAgent")
def test_recovers_from_logic_rejection(mock_coder_cls, mock_critic_cls, mock_summarizer_cls, temp_db):
    memory, session = make_session(temp_db)

    mock_coder_cls.return_value = fake_coder([
        SqlResponse(info="wrong approach", sql_query="SELECT id FROM products"),
        SqlResponse(info="fixed approach", sql_query="SELECT name FROM products WHERE id = 1")
    ])
    mock_critic_cls.return_value = fake_critic([
        SQLCriticVerdict(is_correct=False, critique="Wrong column selected"),
        SQLCriticVerdict(is_correct=True, critique="")
    ])
    mock_summarizer_cls.return_value.summarize.return_value = "summary"

    result = sql_main.run_sql_healing_pipeline(user_query="get widget name", session=session, memory=memory)

    assert result is not None
    assert "Widget" in result
    assert mock_coder_cls.return_value.generate_sql_query.call_count == 2
    assert mock_critic_cls.return_value.evaluate_logic.call_count == 2


@patch("sql_main.SummarizerAgent")
@patch("sql_main.SqlCriticAgent")
@patch("sql_main.SqlCoderAgent")
def test_gives_up_after_max_retries(mock_coder_cls, mock_critic_cls, mock_summarizer_cls, temp_db):
    memory, session = make_session(temp_db)

    mock_coder_cls.return_value = fake_coder([
        SqlResponse(info="always wrong", sql_query="SELECT id FROM products") for _ in range(4)
    ])
    mock_critic_cls.return_value = fake_critic([
        SQLCriticVerdict(is_correct=False, critique="never right") for _ in range(4)
    ])

    result = sql_main.run_sql_healing_pipeline(user_query="impossible", session=session, memory=memory, max_retries=4)

    assert result is None
    assert mock_coder_cls.return_value.generate_sql_query.call_count == 4
    mock_summarizer_cls.return_value.summarize.assert_not_called()


@patch("sql_main.SummarizerAgent")
@patch("sql_main.SqlCriticAgent")
@patch("sql_main.SqlCoderAgent")
def test_only_successful_code_saved_to_memory(mock_coder_cls, mock_critic_cls, mock_summarizer_cls, temp_db):
    memory, session = make_session(temp_db)

    mock_coder_cls.return_value = fake_coder([
        SqlResponse(info="bad", sql_query="SELECT nonexistent_col FROM products"),
        SqlResponse(info="good", sql_query="SELECT name FROM products WHERE id = 1")
    ])
    mock_critic_cls.return_value = fake_critic([
        SQLCriticVerdict(is_correct=True, critique="")
    ])
    mock_summarizer_cls.return_value.summarize.return_value = "did the thing"

    sql_main.run_sql_healing_pipeline(user_query="get widget name", session=session, memory=memory)

    assert len(session.history) == 1
    assert "nonexistent_col" not in session.history[0].successful_code
    assert "SELECT name FROM products" in session.history[0].successful_code