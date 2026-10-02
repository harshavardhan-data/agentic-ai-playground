from pydantic import BaseModel
from typing import Any

class ColumnInfo(BaseModel):
    name: str
    data_type: str
    
class TableInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]


class SchemaInspectionResult(BaseModel):
    tables: list[TableInfo]



class DataFrameColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool


class DataFrameInspectionResult(BaseModel):
    row_count: int
    column_count: int
    columns:list[DataFrameColumnInfo]