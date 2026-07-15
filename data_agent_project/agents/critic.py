from google import genai
from google.genai import types
from agents.models import CriticVerdict
from core.logger import get_logger

logger=get_logger(__name__)

class CriticAgent:
    
    def __init__(self,client=genai.Client,model:str="gemini-3.1-flash-lite"):
        self.client=client
        self.model=model
        
    
    def evaluate_logic(self,query:str,schema:str,code:str,output:str) -> CriticVerdict:
        logger.info("Invoking Critic Agent logic verification audit")

        critic_prompt = f"""You are an elite code reviewer and data auditor.
        User Original Query: {query}
        Dataset Schema: {schema}

        The Coder Agent wrote this code:
        {code}

        The code ran and printed this exact output:
        {output}

        Analyze the code logic. Did it accurately answer the user's query? Did it handle discounts, missing values, or other parameters specified?
        Output your verdict strictly using the schema."""
        
        response=self.client.models.generate_content(
            model=self.model,
            contents=critic_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CriticVerdict
            )
        )
        logger.info("Critic review cycle concluded")
        return CriticVerdict.model_validate_json(response.text)
    