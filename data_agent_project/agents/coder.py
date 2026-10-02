from typing import List
from google import genai
from google.genai import types
from models.llm_schemas import CodeResponse
from core.logger import get_logger
from core.memory import MemoryTurn,SessionState
from prompts.formatter import PromptFormatter
from core.telemetry import log_call,log_token_usage

logger=get_logger(__name__)



def execute_generated_code(code_str:str):
    eval(code_str)

class CoderAgent:

    def __init__(self,client:genai.Client,model:str="gemini-3.1-flash-lite"):
        self.client=client
        self.model=model
    
    @log_call   
    def generate_code(self,current_task:str,csv_schema:str,session:SessionState,retry_context:str="") ->CodeResponse:
        # Observability: Log context history depth
        logger.info("Compiling prompt with session conversation history",extra={"extra_data":{"history_depth":len(session.history),"session_id": session.session_id}})

        
        history_section=PromptFormatter.format_history(session)
        sandbox_section=PromptFormatter.format_sandbox(session)

        current_prompt = f"""You are an expert Python data analysis agent. 
        Important Execution Rules :
        - The Python execution environment is persitent across this session
        - Variables created during previous successful executions are still available to you
        - Reuse existing variables whenever appropriate.
        - Do not hardcode numerical outputs
        - Only recompute values when necessary
        - Assume a pandas DataFrame named 'df' is already loaded in the environment
        - Always finish by printing the requested result

        {PromptFormatter.build_section("CURRENT TASK",current_task)}

        {PromptFormatter.build_section("CSV Schema",csv_schema)}
        
        {PromptFormatter.build_section("ATTEMPTS SO FAR THIS TASK (all failed — do not repeat these mistakes)", retry_context)}

        {PromptFormatter.build_section("SESSION HISTORY",history_section)}

        {PromptFormatter.build_section("CURRENT EXECUTION STATE",sandbox_section)}
       

        """

        

        logger.info("Invoking Coder Agent generation workflow")
        response=self.client.models.generate_content(
            model=self.model,
            contents=current_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CodeResponse
            )
        )
        
        log_token_usage(response=response,agent_name="Coder")

        # SDE Observability: Capture metadata without disrupting streaming flow
        logger.info("Coder generation complete.", extra={"extra_data": {"model": self.model,"session_id": session.session_id}})
        return CodeResponse.model_validate_json(response.text)
    