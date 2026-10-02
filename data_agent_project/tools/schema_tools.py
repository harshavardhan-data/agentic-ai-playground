import sqlite3
from models.schema import ColumnInfo,TableInfo,SchemaInspectionResult
from models.tool_context import ToolContext
from models.tool_input_schemas import SchemaInspectionInput
from models.execution_results import ToolExecutionResult,ToolStatus
from tools.registry import registry


@registry.register(scope="sql",input_schema=SchemaInspectionInput)
def inspect_schema(__context:ToolContext,) -> ToolExecutionResult:

    db_path=__context.session.sandbox_state.get("db_path")

    if not db_path:
        return ToolExecutionResult.failure(tool_name="inspect_schema",status=ToolStatus.EXECUTION_ERROR,
                                           error_msg="No database loaded in the current session")
    
    with sqlite3.connect(db_path) as conn:
        cursor=conn.cursor()

        cursor.execute(
            """SELECT name FROM sqlite_master 
               WHERE type='table'
               AND name NOT LIKE 'sqlite%'
               ORDER BY name
               """
        )

        tables=[row[0] for row in cursor.fetchall()]

        table_infos=[]

        for table_name in tables:
            columns=cursor.execute(
                f"PRAGMA table_info('{table_name}')"
            ).fetchall()


            table_infos.append(
                TableInfo(name=table_name,
                          columns=[
                            ColumnInfo(name=row[1],data_type=row[2])
                            for row in columns
                          ],
                          )
                 )
        output=SchemaInspectionResult(tables=table_infos)

        return ToolExecutionResult.ok(tool_name="inspect_schema",output=output.model_dump(),status=ToolStatus.SUCCESS)


    


    