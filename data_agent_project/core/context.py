from dataclasses import dataclass
from core.memory import SessionState

@dataclass
class OrchestratorContext:
    user_query: str
    conversation_summary : str
    recent_history: str
    available_resources: list[str]
    available_tools: list[str]
    available_scopes: list[str]



@dataclass
class AvailableResource:
    type: str
    description: str

class ContextBuilder:

    @classmethod
    def build(cls,user_query:str,session:SessionState,registry) -> OrchestratorContext:

        conversation_summary="\n".join(turn.summary for turn in session.history[-2:]) 

        recent_turns=session.history[-3:]
        recent_history = "\n\n".join(
        f"User: {t.user_query}\n\tSummary: {t.summary}"
        for t in recent_turns
        )

        resources=[]
        scopes=["global"]

        # tools=registry.list_tool_names()

        if "df" in session.sandbox_state:
            resources.append(AvailableResource(type="dataframe",description="An uploaded tabular dataframe is available"))
            scopes.append("data")

        if "db_path" in session.sandbox_state:
            resources.append(AvailableResource(type="database",description="Sqlite Database available"))
            scopes.append("sql")

        tools=registry.list_tool_names(scopes)

        return OrchestratorContext(user_query=user_query,conversation_summary=conversation_summary,
                                   recent_history=recent_history,available_resources=resources,available_tools=tools,available_scopes=scopes)




        