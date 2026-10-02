# from tools.schema_tools import inspect_schema
from tools.registry import registry
from models.tool_context import ToolContext
from core.sqlite_memory import SessionState,SqliteSessionStore
from models.execution_results import ToolExecutionResult
import pytest
import pandas as pd
from tools import dataframe_tools



def test_sql_schema_extraction():

    # db_path="databases/test_sales.db"

    session=SessionState(session_id="testing_123")
    memory=SqliteSessionStore()

    result=registry.execute_tool("inspect_schema",
                          arguments={},
                          tool_context=ToolContext(session=session,memory=memory))



    print(result.status,result.error_msg)

    assert isinstance(result,ToolExecutionResult)
    assert result.output is None

def test_dataframe_inspection():

    session=SessionState(session_id="testing_123")
    memory=SqliteSessionStore()
    df=pd.read_csv('../test_sales.csv')
    session.sandbox_state['df']=df

    result=registry.execute_tool("inspect_dataframe",arguments={},tool_context=ToolContext(session=session,memory=memory))

    print(result.output)
    print(type(result.output))


def test_data_profiling():
      session=SessionState(session_id="testing_123")
      memory=SqliteSessionStore()
      df=pd.read_csv('../test_sales.csv')
      session.sandbox_state['df']=df

      result=registry.execute_tool("profile_dataset",arguments={},tool_context=ToolContext(session=session,memory=memory))

      print(result.output)
        

if __name__ == "__main__":
    # test_sql_schema_extraction()
    # test_dataframe_inspection()
    test_data_profiling()
