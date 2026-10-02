from pydantic import BaseModel

class ColumnProfile(BaseModel):
    name: str
    dtype: str
    missing_count: int
    missing_pct: float
    unique_count: int

class NumericProfile(BaseModel):
    min:float | None
    max:float | None
    mean:float | None
    median:float | None


class DataProfileResult(BaseModel):
    row_count:int
    column_count:int
    columns:list[ColumnProfile]
    numeric_profiles:dict[str,NumericProfile]

    

