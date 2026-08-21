from enum import Enum
from main import run_self_healing_pipeline
from sql_main import run_sql_healing_pipeline

class AgentType(str,Enum):

    DATA_ANALYSIS="data_analysis"
    SQL="sql"

def classify_query(session) -> AgentType:
         if "df" in session.sandbox_state or "csv_path" in session.sandbox_state:
            return AgentType.DATA_ANALYSIS

         if "db_path" in session.sandbox_state:
             return AgentType.SQL

         raise ValueError("No execution context loaded.")    

def route_query(user_query, session, **kwargs):

    agent = classify_query(session)

    if agent == AgentType.DATA_ANALYSIS:
        return run_self_healing_pipeline(
            user_query=user_query,
            session=session,
            **kwargs
        )

    if agent == AgentType.SQL:
        return run_sql_healing_pipeline(
            user_query=user_query,
            session=session,
            **kwargs
        )