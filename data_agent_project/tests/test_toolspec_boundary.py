from tools.registry import registry
from models.tool_context import ToolContext
from core.memory import SessionState
from core.sqlite_memory import SqliteSessionStore


session=SessionState(session_id="mayya123",history=[])
memory=SqliteSessionStore()

result=registry.execute_tool(
    tool_name="run_sql_analysis",
    arguments={"user_query":"Calculate total Electronics Revenue","faze_update":"Hello World"},
    tool_context=ToolContext(session=session,memory=memory),
)

print(result)