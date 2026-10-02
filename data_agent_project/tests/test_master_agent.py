# from core.context import OrchestratorContext
# from prompts.master_prompt import MasterPrompt
from agents.master_agent import MasterAgent
from tools.registry import registry
from unittest.mock import MagicMock,patch
# from core.memory import SessionState
from core.context import ContextBuilder
from tools import schema_tools

# context=OrchestratorContext(
#         user_query="Calculate Revenue",
#         conversation_summary="User previously analyzed sales.",
#         recent_history="Turn 1: Revenue analysis",
#         available_resources=["SQLite database connected"],
#         available_tools=["run_sql_pipeline"],
#         available_scopes=["global", "sql"],
#     )

# context1=OrchestratorContext(
#         user_query="Hello",
#         conversation_summary="",
#         recent_history="",
#         available_resources=[],
#         available_tools=[],
#         available_scopes=["global"],
#     )

# def test_master_prompt_build():

#     prompt=MasterPrompt.build(context)

#     assert isinstance(prompt,str)
#     assert "Calculate Revenue" in prompt
#     assert "SQLite database connected" in prompt
#     assert "run_sql_pipeline" in prompt


# def test_run_builds_prompt_and_sends_to_chat():
#     fake_client = MagicMock()
#     fake_registry = MagicMock()

#     def tool_a(): pass
#     def tool_b(): pass
#     fake_registry.get_tools_for_scope.return_value = [tool_a, tool_b]   # real functions, not strings

#     agent = MasterAgent(client=fake_client, registry=fake_registry)

#     fake_chat = MagicMock()
#     fake_client.chats.create.return_value = fake_chat

#     fake_context = MagicMock()
#     fake_context.available_scopes = ["global"]
#     fake_session = MagicMock()

#     with patch("agents.master_agent.MasterPrompt") as mock_prompt_cls:
#         mock_prompt_cls.build.return_value = "BUILT_PROMPT_TEXT"

#         agent.run(context=fake_context, session=fake_session, registry=fake_registry)

#         mock_prompt_cls.build.assert_called_once_with(fake_context)
#         fake_registry.get_tools_for_scope.assert_called_once_with(["global"])
#         fake_client.chats.create.assert_called_once()
#         fake_chat.send_message.assert_called_once_with("BUILT_PROMPT_TEXT")


def make_function_call(name, args=None):
    call = MagicMock()
    call.name = name
    call.args = args or {}
    return call


def test_master_schema_then_sql():
    # -------------------------
    # Fake Gemini responses
    # -------------------------

    # ---------------------------------------------------------------
    # 2. FAKE GEMINI RESPONSES (Turn 1 -> Turn 2 -> Turn 3)
    # ---------------------------------------------------------------
    # Turn 1: Gemini requests inspect_schema
    response_1 = MagicMock()
    response_1.function_calls = [make_function_call("inspect_schema")]

    # Turn 2: Gemini receives schema, requests SQL execution
    response_2 = MagicMock()
    response_2.function_calls = [
        make_function_call(
            "run_sql_analysis",
            {
                "user_query": (
                    "Using the transactions table, calculate total revenue for Electronics."
                )
            },
        )
    ]

    # Turn 3: Gemini finishes planning and returns final text
    response_3 = MagicMock()
    response_3.function_calls = []
    response_3.text = "The total revenue for Electronics is $3,730.49."

    # Gemini Chat Mock: Handles 3 turns sequentially
    mock_chat = MagicMock()
    mock_chat.send_message.side_effect = [
        response_1,
        response_2,
        response_3,
    ]

    mock_client = MagicMock()

    # ---------------------------------------------------------------
    # 3. SETUP SESSION & CONTEXT
    # ---------------------------------------------------------------
    session = MagicMock()
    session.sandbox_state = {"db_path": "databases/test_sales.db"}
    session.history = []

    memory = MagicMock()

    master = MasterAgent(mock_client,registry=registry)

    context = ContextBuilder.build(
        user_query="What is the total revenue from Electronics?",
        session=session,
        registry=registry,
    )

    # ---------------------------------------------------------------
    # 4. EXECUTE MASTER AGENT
    # ---------------------------------------------------------------
    with patch.object(master, "_create_chat", return_value=mock_chat), \
        patch("tools.analysis_tools.run_sql_healing_pipeline") as mock_pipeline:


        # Force the SQL pipeline to succeed when invoked
        mock_pipeline.return_value = "Total revenue for Electronics is $3,730.49."
    
        result = master.run(
            context=context,
            session=session,
            memory=memory,
        )
    

    # ---------------------------------------------------------------
    # 5. ASSERTIONS
    # ---------------------------------------------------------------
    # Final textual answer returned to caller
    assert result == "The total revenue for Electronics is $3,730.49."

    # Gemini chat send_message called 3 times:
    # Call 1: Initial prompt -> returns response_1 (inspect_schema)
    # Call 2: Schema result -> returns response_2 (run_sql_analysis)
    # Call 3: SQL result    -> returns response_3 (final text)
    assert mock_chat.send_message.call_count == 3

    # Inspect function calls requested on turn 1 and 2
    assert response_1.function_calls[0].name == "inspect_schema"
    assert response_2.function_calls[0].name == "run_sql_analysis"


if __name__=='__main__':
    pass