import os
import pandas as pd
from google import genai
from core.logger import get_logger
from sandboxes.code_sandbox import CodeSandbox
from agents.coder import CoderAgent
from agents.critic import CriticAgent
from google import genai
from core.memory import BaseSessionStore,MemoryTurn,SessionState
from agents.summarizer import SummarizerAgent
from prompts.formatter import PromptFormatter
import time
from models.pipeline_errors import PipelineException,PipelineStage



logger=get_logger(__name__)

def run_self_healing_pipeline(user_query:str,
                              memory:BaseSessionStore,session:SessionState,
                              max_retries:int=4,client:genai.Client=None):
    
    pipeline_start = time.perf_counter()  # — tracks total time across all retries


    try:

    # Agents now use the shared singleton client!
        coder = CoderAgent(client=client)
        critic = CriticAgent(client=client)
        summarizer = SummarizerAgent(client=client)

        session_id=session.session_id
        
        sandbox_state=session.sandbox_state

        csv_schema=CodeSandbox.build_schema_string(session.sandbox_state["df"])
    except Exception as e:
        raise PipelineException("Unable to load the Schema/initilialize the client",stage=PipelineStage.SCHEMA_EXTRACTION,is_fatal=True) from e
    
    attempts=[]

    
    for attempt in range(1,max_retries+1):
        attempt_start = time.perf_counter() # - per attempt timing
        logger.info(f"Initiating pipeline processing loop execution cycle.", extra={"extra_data": {"attempt": attempt,"session_id": session_id}})

        try:
        # Inject context history directly into generation step
            agent_response=coder.generate_code(user_query,csv_schema,session,retry_context=PromptFormatter.format_retry_attempts(attempts))
            logger.info("Coder rationale", extra={"extra_data": {"info": agent_response.info,"session_id": session_id}}) 
        except Exception as e:
            logger.error("Code generation failed", extra={"stage": PipelineStage.CODE_GENERATION, "error": str(e)})
            attempts.append({"code": "N/A", "status": "Generation Error", "feedback": str(e)})
            continue

        # 2. Execute within isolated Sandbox architecture
       
        sandbox_result=CodeSandbox.execute(agent_response.code,sandbox_state)

        attempt_duration_ms = round((time.perf_counter() - attempt_start) * 1000, 2)  


        if not sandbox_result.success:
            logger.warning(f"Execution runtime crash or safety breach intercepted.", 
                           extra={"extra_data": {"attempt": attempt,"stage":PipelineStage.SANDBOX_EXECUTION,"duration_ms": attempt_duration_ms,"session_id": session_id}})
            
            attempts.append({
                "code":CodeSandbox.clean_code(agent_response.code),
                "status":"Execution Error",
                "feedback":sandbox_result.error_message
            })
            continue
        
        logger.info(f"Sandbox execution successfully processed raw script output: {sandbox_result.result}")

        # 3. Evaluate logic via Context-Isolated Critic Agent
        verdict=critic.evaluate_logic(
            query=user_query,
            schema=csv_schema,
            code=agent_response.code,
            output=sandbox_result.result,
            session=session
        )


        if verdict.is_correct :
            total_duration_ms = round((time.perf_counter() - pipeline_start) * 1000, 2)
            logger.info("Pipeline successful. System state approved by internal auditor.",extra={
                        "extra_data":{"attempts_used":attempt,
                                      "total_duration_ms":total_duration_ms,
                                      "last_attempt_duration_ms":attempt_duration_ms,"session_id": session_id}})
            # SDE State Persistence: Commit only the successful final execution path to long-term memory
            try:
                summary=summarizer.summarize(user_query=user_query,code=agent_response.code,output=sandbox_result.result)
                new_turn=MemoryTurn(user_query=user_query,
                                    successful_code=CodeSandbox.clean_code(agent_response.code),
                                    execution_output=sandbox_result.result,summary=summary)
                memory.add_turn(session,new_turn)
                logger.info("Pipeline successful. Turn committed to session memory state store.")     
            except Exception as e:
                logger.error("Failed persisting memory state, proceeding to return output", 
                                             extra={"stage": PipelineStage.MEMORY_PERSISTENCE, "error": str(e)})
            return sandbox_result.result
        else:
            logger.warning(f"Logic failure rejected by auditor. Context loop updated.", 
                           extra={"extra_data": {"critique": verdict.critique,"duration_ms":attempt_duration_ms,"session_id": session_id}})
            attempts.append({
            "code": CodeSandbox.clean_code(agent_response.code),
            "status": "Rejected by Critic",
            "feedback": verdict.critique
            })

    total_duration_ms = round((time.perf_counter() - pipeline_start) * 1000, 2)  # NEW
    last_feedback = attempts[-1]['feedback'] if attempts else 'n/a'
    last_status = attempts[-1]['status'] if attempts else 'unknown'
    logger.error(
        "Pipeline reached maximum configured loop iteration boundary without analytical resolution.",
        extra={"extra_data": { 
            "attempts_used": max_retries,
            "total_duration_ms": total_duration_ms,
            "final_failure_status": last_status,
            "final_failure_feedback": last_feedback,
            "session_id": session_id
        }}
    )
    return PipelineException(
        f"Python Pipeline reached max retries ({max_retries}). Last feedback: {last_feedback}, Last Staus:{last_status}",
        stage=PipelineStage.SANDBOX_EXECUTION,
        is_fatal=True
    )

if __name__ == "__main__":
   pass