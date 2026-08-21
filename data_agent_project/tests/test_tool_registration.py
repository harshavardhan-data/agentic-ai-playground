import tools
from tools.registry import registry 
import inspect
import pytest


def test_pipeline_tools_registered():

    sql_tools=registry.get_tools_for_scope(['sql'])
    data_tools=registry.get_tools_for_scope(['data'])


    sql_names = [tool.__name__ for tool in sql_tools]
    data_names = [tool.__name__ for tool in data_tools]

    assert "run_sql_analysis" in sql_names
    assert "run_data_analysis" in data_names


def test_hidden_parameters_are_masked():

    sql_tools = registry.get_tools_for_scope(["sql"])

    sql_tool = next(
        tool for tool in sql_tools
        if tool.__name__ == "run_sql_analysis"
    )

    signature = inspect.signature(sql_tool)

    assert "user_query" in signature.parameters
    assert "__session" not in signature.parameters
    assert "__memory" not in signature.parameters