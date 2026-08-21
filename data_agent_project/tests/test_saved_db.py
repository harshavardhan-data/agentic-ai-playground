from sqlalchemy import select,create_engine
from sqlalchemy.orm import sessionmaker
from models.db_models import DBSessionModel,DBTurnModel
from core.context import ContextBuilder
from tools.registry import registry
from core.sqlite_memory import SqliteSessionStore

@staticmethod
def format_resources(resources: list) -> str:
    if not resources:
        return "No data resources currently loaded."
    return "\n\t".join(f"- {r.type}: {r.description}" for r in resources)

engine=create_engine("sqlite:///./agent_memory.db")
SessionLocal=sessionmaker(bind=engine)
store=SqliteSessionStore()
with SessionLocal() as db:
    db_sessions=db.scalars(select(DBSessionModel)).all()    

    print("============ Sessions =============\n")
    for db_session in db_sessions:
        if db_session.session_id == "master-sql-test_2":
            print(f"Session ID : {db_session.session_id} , Created At : {db_session.created_at}")

            # Go through the store, same as real request-handling code — get a real SessionState back
            session = store.get_session(db_session.session_id)
            print(f"Sandbox State : {session.sandbox_state}")


            

            session_context=ContextBuilder.build(user_query="So what do we do Now!!",session=session,registry=registry)
            res=format_resources(session_context.available_resources)
            context_build=f"""
            USER QUERY : {session_context.user_query}
                
            CONVERSATION SUMMARY : 
            {session_context.conversation_summary}
                
            RECENT HISTORY : 
            {session_context.recent_history}
                
            AVAILABLE RESOURCES :
            {res}

            AVAILABLE TOOLS : 
            {session_context.available_tools}

            AVAILABLE SCOPES : 
            {session_context.available_scopes}

            """
            print(context_build)
            print("\n\n===================================")

        # print("\n--------------------------------------")
        # for turn in s.turns:
        #     print(f"Turn : {turn.id}")
        #     print(f"\tUser Query :  {turn.user_query}")
        #     print(f"\tSummary : {turn.execution_output}")
        #     print(f"{turn.successful_code}")
        # print("----------------------------------------")

