from dataclasses import dataclass
from typing import Optional,Any
import pandas as pd


@dataclass
class SqlExecutionResult:
    success: bool
    result_df: Optional[pd.DataFrame]
    error_message: Optional[str]
    execution_time_ms: float
    rows_returned: Optional[int]


    @classmethod
    def ok(cls, result_df: pd.DataFrame, execution_time_ms: float) -> "SqlExecutionResult":
        return cls(success=True, result_df=result_df, error_message=None,
                   execution_time_ms=execution_time_ms, rows_returned=len(result_df))

    @classmethod
    def failure(cls, error_message: str, execution_time_ms: float = 0.0) -> "SqlExecutionResult":
        return cls(success=False, result_df=None, error_message=error_message,
                   execution_time_ms=execution_time_ms, rows_returned=None)


@dataclass
class ToolExecutionResult:
    success: bool
    tool_name: str
    output: str
    error_msg: Optional[str]

    @classmethod
    def ok(cls,tool_name:str,output:Any) -> "ToolExecutionResult":
        return cls(success=True,tool_name=tool_name,output=output,error_msg=None)

    @classmethod
    def failure(cls,tool_name:str,error_msg:str) -> "ToolExecutionResult":
        return cls(success=False,tool_name=tool_name,error_msg=error_msg,output=None)


