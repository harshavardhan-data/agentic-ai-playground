from agents.master_agent import MasterAgent
from tools.registry import registry
from core.client import gemini_client
from core.sqlite_memory import SqliteSessionStore,SessionState
from core.context import ContextBuilder
import pandas as pd

def test_master_sql():

    memory=SqliteSessionStore()

    session_id='tool_spec_trial_2'

    session=memory.get_session(session_id)

    df=pd.read_csv("../customers.csv")

    memory.update_sandbox_state(session_id,
                                "db_path","databases/test_sales.db")
    memory.update_sandbox_state(session_id,"df",df)

    session=memory.get_session(session_id)

    user_query = (
        "Calculate the total Electronics revenue from the database,"
        "then tell me the average satisfaction score of Premium customers from the uploaded customer data. Combine both results into one answer."
    )

    context = ContextBuilder.build(
        user_query=user_query,
        session=session,
        registry=registry,
    )

    print(context.available_scopes)
    print(context.available_tools)

    master_agent = MasterAgent(
        client=gemini_client,
        registry=registry,
    )

    result = master_agent.run(
        context=context,
        session=session,
        memory=memory,
    )

    print("\nFINAL ANSWER:")
    print(result)



if __name__ == "__main__":
    test_master_sql()

  
