from typing import List
from google import genai
from google.genai import types
from models.llm_schemas import CriticVerdict
from core.logger import get_logger
from core.memory import MemoryTurn,SessionState
from prompts.formatter import PromptFormatter
from core.telemetry import log_call,log_token_usage

logger=get_logger(__name__)

class CriticAgent:
    
    def __init__(self,client:genai.Client,model:str="gemini-3.1-flash-lite"):
        self.client=client
        self.model=model
        
    @log_call
    def evaluate_logic(self,query:str,schema:str,code:str,output:str,session:SessionState) -> CriticVerdict:
        logger.info("Invoking Critic Agent logic verification audit",extra={"extra_data":{"session_id": session.session_id}})

        history_section=PromptFormatter.format_history(session)
        sandbox_section=PromptFormatter.format_sandbox(session)


        critic_prompt = f"""You are an expert Python code reviewer and data auditor.You are reviewing code generated inside a persistent 
        notebook-style execution environment.
        IMPORTANT ASSESSMENT RULES:
        - Previous successful turns are part of the same execution session,they are in the session history.
        - Variables created during previous successful executions remain available in the current Python execution environment. Reuse them whenever they satisfy the current request instead of recomputing them.
        - The current user query may intentionally refer to previous computations or conversations.
        - Do NOT penalize the code for reusing variables from previous turns.
        - Reject the code only if its intended logic fails to satisfy the curent request.

        {PromptFormatter.build_section("CURRENT USER REQUEST", query)}

        {PromptFormatter.build_section("SESSION HISTORY", history_section)}

        {PromptFormatter.build_section("CURRENT EXECUTION STATE", sandbox_section)}

        {PromptFormatter.build_section("DATASET SCHEMA", schema)}

        {PromptFormatter.build_section("GENERATED CODE", code)}

        {PromptFormatter.build_section("PROGRAM OUTPUT", output)}


       
        Determine whether the generated code correctly satisfies the current request within the context of the entire session.
        Return only the required JSON schema."""
        
        response=self.client.models.generate_content(
            model=self.model,
            contents=critic_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CriticVerdict
            )
        )
        log_token_usage(response=response,agent_name="Critic")
        logger.info("Critic review cycle concluded",extra={"extra_data": {"session_id": session.session_id}})
        return CriticVerdict.model_validate_json(response.text)
    