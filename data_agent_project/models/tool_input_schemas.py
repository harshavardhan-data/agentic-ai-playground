from pydantic import BaseModel,ConfigDict

class AnalysisToolInput(BaseModel):
    user_query: str

    model_config=ConfigDict(extra="forbid")


class SchemaInspectionInput(BaseModel):
    model_config=ConfigDict(extra="forbid")


class DataFrameInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")