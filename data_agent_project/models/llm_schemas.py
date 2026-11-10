from pydantic import BaseModel, Field
from typing import Dict,Literal,List
from models.analysis import Evidence


class CodeResponse(BaseModel):
    info: str = Field(description="Brief explanation of the analytical approach or steps taken.")
    code: str = Field(description="Pure, executable Python code targeting the existing 'df' variable. Do NOT use markdown code blocks or wrap in fences.")

# class CriticVerdict(BaseModel):
#     is_correct: bool = Field(description="True if the code logic perfectly and completely answers the user query. False if it misses math, logic, filters, or parameters.")
#     critique: str = Field(default="",description="If is_correct is False, provide specific feedback on what is wrong or missing. Leave empty if True.")

class SqlResponse(BaseModel):
    info:str=Field(description="Explanation of how you constructed the query")
    sql_query:str=Field(description="The executable SQL query")

class SQLCriticVerdict(BaseModel):
    is_correct: bool = Field(description="True if the query succeeded AND answers the user's question.False if it misses math,logic,filters")
    critique: str = Field(description="Feedback on what went wrong or confirmation of success")


##########################################################################

# class GeneratorResponse(BaseModel):
#     generated_claims:Dict[str,str] =Field(description="Map of finding_id to its generated claim")
class ClaimItem(BaseModel):
    finding_id: str = Field(description="The exact finding_id from the input prompt")
    claim: str = Field(description="The compact one-sentence claim")

class GeneratorResponse(BaseModel):
    claims: List[ClaimItem] = Field(description="List of claims for each finding")



class VerificationPlan(BaseModel):
    artifact_hypothesis:str =Field(description="the specific data artifact that could make this finding invalid,and the exact evidence found for it")
    code_type:Literal['python','sql'] =  Field(description="Type of verification method used")
    code_snippet:str = Field(description="The bulletproof python code or sql query that supports or contradicts the claim")

class CriticVerdict(BaseModel):
    supports:bool=Field(description="True if the provided verification/contradicton is logically correct and justified for the given claim")
    verdict:Literal['contradicted','supports','uncertain']
    proof:str=Field(description="The specific evidence from the given verification code and its thought of origin")
    interpretation:str=Field("What artifacts were checked and what were confirmed/contradicted")
