# agents/tool_agent.py
from core.logger import get_logger
from google import genai
from google.genai import types
from typing import Optional, List, Any
# from tools.registry import registry
from prompts.formatter import PromptFormatter
from core.context import OrchestratorContext
from core.memory import SessionState,BaseSessionStore
from prompts.master_prompt import MasterPrompt
from models.execution_results import ToolExecutionResult


logger = get_logger(__name__)



class MasterAgent:

    def __init__(self,client:genai.Client,model:str="gemini-3.1-flash-lite",registry=None,max_turns:int=5):
        self.client=client
        self.model=model
        self.registry=registry
        self.max_turns=max_turns

    

    def run(self,context:OrchestratorContext,session:SessionState,memory:BaseSessionStore) -> str :

        logger.info("MasterAgent started.")

        prompt= MasterPrompt.build(context)

        chat=self._create_chat(context)

        response=chat.send_message(prompt)

        logger.info("MasterAgent produced initial response.")

        turns=0

        while response.function_calls:
            logger.info("Entered into the Main Loop")

            turns+=1

            if turns>self.max_turns:
                raise RuntimeError("MasterAgent exceeded planning limit.")

            tool_results=self._execute_tool_calls(response.function_calls,session,memory,context)

            response=self._send_tool_results(chat,tool_results,)
            
            
        logger.info("Planning Completed")

        return response.text



    def _create_chat(self,context:OrchestratorContext):

        tools=self.registry.get_tools_for_scope(context.available_scopes)

        config=types.GenerateContentConfig(tools=tools,temperature=0.2,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))

        return self.client.chats.create(
            model=self.model,
            config=config
        )
        


    def _execute_tool_calls(self,function_calls,session:SessionState,memory:BaseSessionStore,context:OrchestratorContext) -> List[ToolExecutionResult]:

        results=[]

        for call in function_calls:

            tool_name=call.name
            model_args=call.args or {}

            logger.info(
                f"Gemini proposed tool '{tool_name}' "
                f"with args: {model_args}"
    )       
            

            logger.info(
                f"Application will execute '{tool_name}' "
                f"with args: {model_args}"
            )


            result=self.registry.execute_tool(
                tool_name=tool_name,
                arguments=model_args,
                session_state=session,
                memory=memory
            )

            results.append(result)

        return results


    def _send_tool_results(self,chat,results:list[ToolExecutionResult],):
        parts=[]

        for result in results:
            parts.append(
                types.Part.from_function_response(
                    name=result.tool_name,
                    response={
                        "success":result.success,
                        "tool_name":result.tool_name,
                        "output":result.output,
                        "error":result.error_msg,
                    },
                )
            )

        return chat.send_message(parts)
    

   










