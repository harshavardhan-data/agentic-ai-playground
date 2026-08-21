from tools.registry import registry
from typing import Any
from sql_main import run_sql_healing_pipeline
from main import run_self_healing_pipeline
from core.memory import SessionState,BaseSessionStore

@registry.register(scope="sql")
def run_sql_analysis(user_query:str,__session:SessionState,__memory:BaseSessionStore) -> Any:
    """
    Execute the SQL analysis pipeline for the user's request.

    user_query:
        The user's original natural-language analytical request.
        Pass it as the request itself, not as generated SQL.
        The SQL specialist is responsible for generating SQL.
    """
    return run_sql_healing_pipeline(user_query=user_query,session=__session,memory=__memory)


@registry.register(scope="data")
def run_data_analysis(user_query:str,__session:SessionState,__memory:BaseSessionStore) -> Any:
    """
    Run the complete self-healing dataframe analysis pipeline
    against the dataset associated with the current session.
    """
    return run_self_healing_pipeline(user_query=user_query,session=__session,memory=__memory)