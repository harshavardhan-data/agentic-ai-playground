from dataclasses import dataclass
from typing import Optional,Any
import pandas as pd
from enum import Enum


@dataclass 
class PythonExecutionResult:
    success:bool
    result: Optional[str]
    error_message: Optional[str]
    execution_time_ms : float

    @classmethod
    def ok(cls,result:Any,execution_time_ms:float) ->"PythonExecutionResult" :
        return cls(success=True,result=result,execution_time_ms=execution_time_ms,error_message=None)

    @classmethod
    def failure(cls,error_message: str,execution_time_ms=0.0) ->"PythonExecutionResult" :
        return cls(success=False,result=None,execution_time_ms=execution_time_ms,error_message=error_message)

    
        
    

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
    output: Any
    status: str
    error_msg: Optional[str]

    @classmethod
    def ok(cls,tool_name:str,output:Any,status:str="Success") -> "ToolExecutionResult":
        return cls(success=True,tool_name=tool_name,output=output,status=status,error_msg=None,)

    @classmethod
    def failure(cls,tool_name:str,error_msg:str,status:str="Execution Failure") -> "ToolExecutionResult":
        return cls(success=False,tool_name=tool_name,status=status,error_msg=error_msg,output=None)




class ToolStatus(str, Enum):
    SUCCESS = "success"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT = "timeout"
    EXECUTION_ERROR="execution-error"
    INTERNAL_ERROR = "internal_error"
    CONFIGURATION_ERROR="configuration_error"
    RECOVERABLE_ERROR="recoverable_error"
    FATAL_ERROR="fatal_error"