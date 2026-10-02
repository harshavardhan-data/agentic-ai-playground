from unittest.mock import MagicMock,patch
import unittest
import sqlite3
from tools.analysis_tools import run_sql_analysis
from sql_main import run_sql_healing_pipeline
from agents.master_agent import MasterAgent
import pytest
from models.pipeline_errors import PipelineException, PipelineStage
from sandboxes.sql_sandbox import SqlSandbox
from models.execution_results import ToolStatus


      

def test_fatal_error_test():

    # Setup mock session & memory
    mock_session = MagicMock()
    mock_session.session_id = "test_123"
    mock_session.sandbox_state = {"db_path": "corrupted.db"}
    mock_memory = MagicMock()

    # 1. Patch get_schema to raise a raw SQLite driver exception
    with patch("sandboxes.sql_sandbox.SqlSandbox.get_schema") as mock_get_schema:
        raw_sqlite_error = sqlite3.OperationalError("unable to open database file")
        mock_get_schema.side_effect = raw_sqlite_error

        # 2. Run pipeline and verify it raises a fatal PipelineException
        with pytest.raises(PipelineException) as exc_info:
            run_sql_healing_pipeline(
                user_query="Get total revenue",
                session=mock_session,
                memory=mock_memory,
                max_retries=2
            )

        # 3. Assert exception metadata and chaining ('from e')
        pe = exc_info.value
        print(pe)
        print(pe.__cause__)
        assert pe.status == ToolStatus.FATAL_ERROR
        assert pe.metadata["stage"] == PipelineStage.SCHEMA_EXTRACTION
        assert pe.__cause__ is raw_sqlite_error




def test_master_agent_fatal_error_flow():
    # STEP 1: Instantiate MasterAgent with max_turns threshold
    mock_client=MagicMock()
    master = MasterAgent(mock_client)
    master.max_turns = 5

    # STEP 2: Mock context, session, memory inputs required by run()
    mock_context = MagicMock()
    mock_session = MagicMock()
    mock_memory = MagicMock()

    # STEP 3: Mock internal methods called BEFORE the while loop
    with patch.object(master, "_create_chat") as mock_create_chat, \
         patch.object(master, "_execute_tool_calls") as mock_execute_tool_calls, \
         patch.object(master, "_send_tool_results") as mock_send_tool_results:

        # Mock initial chat response containing 1 function call to enter the while loop
        mock_chat = MagicMock()
        mock_initial_response = MagicMock()
        mock_initial_response.function_calls = [MagicMock(name="sql_tool")]
        mock_chat.send_message.return_value = mock_initial_response
        mock_create_chat.return_value = mock_chat

        # STEP 4: Configure _execute_tool_calls to return a FATAL_ERROR ToolResult
        fatal_result = MagicMock()
        fatal_result.status = ToolStatus.FATAL_ERROR
        fatal_result.tool_name = "sql_tool"
        mock_execute_tool_calls.return_value = [fatal_result]

        # STEP 5: Run master.run() and assert RuntimeError is raised
        with pytest.raises(RuntimeError) as exc_info:
            master.run(context=mock_context, session=mock_session, memory=mock_memory)

        # STEP 6: Verify exact exception message and halting behavior
        assert "Fatal tool failure : sql_tool" in str(exc_info.value)
        
        # Proves MasterAgent STOPPED immediately and never called _send_tool_results
        assert mock_send_tool_results.call_count == 0

def test_recoverable_sandbox_retry_loop():
    mock_session = MagicMock()
    mock_session.session_id = "test_123"
    mock_session.sandbox_state = {"db_path": "valid.db"}
    mock_memory = MagicMock()

    with patch("sandboxes.sql_sandbox.SqlSandbox.get_schema", return_value="users: id (INT)"), \
         patch("sandboxes.sql_sandbox.SqlSandbox.get_database_context", return_value=MagicMock()), \
         patch("agents.sql_coder.SqlCoderAgent.generate_sql_query") as mock_coder, \
         patch("sandboxes.sql_sandbox.SqlSandbox.execute") as mock_execute, \
         patch("agents.sql_critic.SqlCriticAgent.evaluate_logic") as mock_critic, \
         patch("agents.summarizer.SummarizerAgent.summarize", return_value="Summary"):

        mock_coder.return_value = MagicMock(sql_query="SELECT * FROM users;", info="test")

        from sandboxes.sql_sandbox import SqlExecutionResult
        
        fail_res = SqlExecutionResult.failure(error_message="no such column: total_revenue")
        
        mock_df = MagicMock()
        mock_df.to_string.return_value = "id\n1"
        success_res = SqlExecutionResult.ok(result_df=mock_df, execution_time_ms=10.0)

        mock_execute.side_effect = [fail_res, success_res]
        mock_critic.return_value = MagicMock(is_correct=True)

        result_text = run_sql_healing_pipeline(
            user_query="Get total revenue",
            session=mock_session,
            memory=mock_memory,
            max_retries=3
        )

        assert result_text == "id\n1"
        assert mock_execute.call_count == 2


def test_master_agent_recoverable_error_self_correction_flow():

    mock_client=MagicMock()
    master=MasterAgent(mock_client)
    master.max_turns=4

    mock_context = MagicMock()
    mock_session = MagicMock()
    mock_memory = MagicMock()

    with patch.object(master, "_create_chat") as mock_create_chat, \
         patch.object(master, "_execute_tool_calls") as mock_execute_tool_calls, \
         patch.object(master, "_send_tool_results") as mock_send_tool_results:
         
        # ---------------------------------------------------------------
        # STEP 3: BUILD THE TURN-BY-TURN GEMINI RESPONSES
        # ---------------------------------------------------------------
        mock_chat = MagicMock()

        # Response 1: Gemini makes bad tool call (triggers Turn 1)
        resp_turn_1 = MagicMock()
        resp_turn_1.function_calls = [
            MagicMock(name="sql_tool", args={"query": "SELECT * FROM invalid_table"})
        ]

        # Response 2: Gemini receives error payload, self-corrects args (triggers Turn 2)
        resp_turn_2 = MagicMock()
        resp_turn_2.function_calls = [
            MagicMock(name="sql_tool", args={"query": "SELECT * FROM users"})
        ]

        # Response 3: Gemini finishes planning and returns final text (exits loop)
        resp_turn_3 = MagicMock()
        resp_turn_3.function_calls = []
        resp_turn_3.text = "Execution recovered and completed successfully."

        # Connect initial prompt response
        mock_chat.send_message.return_value = resp_turn_1
        mock_create_chat.return_value = mock_chat

        # ---------------------------------------------------------------
        # STEP 4: BUILD THE TOOL RESULTS (TURN 1 FAIL -> TURN 2 SUCCESS)
        # ---------------------------------------------------------------
        # Turn 1 tool result: Recoverable failure
        recoverable_result = MagicMock()
        recoverable_result.status = ToolStatus.RECOVERABLE_ERROR
        recoverable_result.tool_name = "sql_tool"
        recoverable_result.error_message = "sqlite3.OperationalError: no such table: invalid_table"
        recoverable_result.output = None  # Will be populated during branching

        # Turn 2 tool result: Clean execution
        success_result = MagicMock()
        success_result.status = ToolStatus.SUCCESS
        success_result.tool_name = "sql_tool"
        success_result.output = "id: 1, name: Alice"

        # Sequential returns for _execute_tool_calls
        mock_execute_tool_calls.side_effect = [
            [recoverable_result],  # Call 1 returns failure
            [success_result]       # Call 2 returns success
        ]

        # Sequential returns for _send_tool_results back to Gemini
        mock_send_tool_results.side_effect = [
            resp_turn_2,  # After Turn 1 results sent, Gemini returns modified args
            resp_turn_3   # After Turn 2 results sent, Gemini returns final text
        ]

        # ---------------------------------------------------------------
        # STEP 5: EXECUTE MASTERAGENT
        # ---------------------------------------------------------------
        final_output = master.run(context=mock_context, session=mock_session, memory=mock_memory)

        # ---------------------------------------------------------------
        # STEP 6: VERIFY FLOW & SELF-CORRECTION BEHAVIOR
        # ---------------------------------------------------------------
        # A. Verify total loop iterations
        assert mock_execute_tool_calls.call_count == 2
        assert mock_send_tool_results.call_count == 2

        # B. Inspect Turn 1 output formatting (Verify MasterAgent updated output payload with nudge/error)
        turn_1_sent_results = mock_send_tool_results.call_args_list[0][0][1]
        sent_fail_result = turn_1_sent_results[0]
        
        assert sent_fail_result.status == ToolStatus.RECOVERABLE_ERROR
        assert "no such table: invalid_table" in sent_fail_result.error_message

        # C. Verify final string output returned to user
        assert final_output == "Execution recovered and completed successfully."



if __name__ == "__main__":
    #  test_fatal_error_test()
    # test_master_agent_fatal_error_flow()
    # test_recoverable_sandbox_retry_loop()
    pass







