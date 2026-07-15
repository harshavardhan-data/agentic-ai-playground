from pydantic import BaseModel, Field

class CodeResponse(BaseModel):
    info: str = Field(description="Brief explanation of the analytical approach or steps taken.")
    code: str = Field(description="Pure, executable Python code targeting the existing 'df' variable. Do NOT use markdown code blocks or wrap in fences.")

class CriticVerdict(BaseModel):
    is_correct: bool = Field(description="True if the code logic perfectly and completely answers the user query. False if it misses math, logic, filters, or parameters.")
    critique: str = Field(description="If is_correct is False, provide specific feedback on what is wrong or missing. Leave empty if True.")