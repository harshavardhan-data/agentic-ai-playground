from core.context import OrchestratorContext
from prompts.master_prompt import MasterPrompt
from agents.master_agent import MasterAgent
from core.client import gemini_client
from tools.registry import registry
from unittest.mock import MagicMock,patch
from core.memory import SessionState

context=OrchestratorContext(
        user_query="Calculate Revenue",
        conversation_summary="User previously analyzed sales.",
        recent_history="Turn 1: Revenue analysis",
        available_resources=["SQLite database connected"],
        available_tools=["run_sql_pipeline"],
        available_scopes=["global", "sql"],
    )

context1=OrchestratorContext(
        user_query="Hello",
        conversation_summary="",
        recent_history="",
        available_resources=[],
        available_tools=[],
        available_scopes=["global"],
    )

def test_master_prompt_build():

    

    prompt=MasterPrompt.build(context)

    assert isinstance(prompt,str)
    assert "Calculate Revenue" in prompt
    assert "SQLite database connected" in prompt
    assert "run_sql_pipeline" in prompt

# def test_create_chat():
#     agent=MasterAgent(client=gemini_client,registry=registry)

#     chat=agent._create_chat(context)

#     assert chat is not None


def test_run_builds_prompt_and_sends_to_chat():
    fake_client = MagicMock()
    fake_registry = MagicMock()

    def tool_a(): pass
    def tool_b(): pass
    fake_registry.get_tools_for_scope.return_value = [tool_a, tool_b]   # real functions, not strings

    agent = MasterAgent(client=fake_client, registry=fake_registry)

    fake_chat = MagicMock()
    fake_client.chats.create.return_value = fake_chat

    fake_context = MagicMock()
    fake_context.available_scopes = ["global"]
    fake_session = MagicMock()

    with patch("agents.master_agent.MasterPrompt") as mock_prompt_cls:
        mock_prompt_cls.build.return_value = "BUILT_PROMPT_TEXT"

        agent.run(context=fake_context, session=fake_session, registry=fake_registry)

        mock_prompt_cls.build.assert_called_once_with(fake_context)
        fake_registry.get_tools_for_scope.assert_called_once_with(["global"])
        fake_client.chats.create.assert_called_once()
        fake_chat.send_message.assert_called_once_with("BUILT_PROMPT_TEXT")


if __name__=='__main__':
    # test_master_prompt_build()
    # test_run_builds_prompt_and_sends_to_chat()
    agent=MasterAgent(client=gemini_client,registry=registry)
    print(agent.run(context=context1,session=SessionState()))