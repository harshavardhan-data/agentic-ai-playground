import time
from core.logger import get_logger
from sandboxes.sql_sandbox import SqlSandbox
from agents.sql_coder import SqlCoderAgent
from agents.sql_critic import SqlCriticAgent
from agents.summarizer import SummarizerAgent
from google import genai
from core.memory import BaseSessionStore,MemoryTurn,SessionState
from prompts.formatter import PromptFormatter
from models.pipeline_errors import PipelineException,PipelineStage


logger=get_logger(__name__)


def run_sql_healing_pipeline(user_query:str,session:SessionState,
                             memory:BaseSessionStore,max_retries:int=4,client:genai.Client=None):

    pipeline_start=time.perf_counter()
    logger.info("SQL pipeline received user query",extra={"extra_data": {"user_query": user_query}}
    )

    session_id=session.session_id

    # STAGE 1: Context & Schema Extraction
    try:
        db_schema=SqlSandbox.get_schema(session.sandbox_state["db_path"])

        db_context=SqlSandbox.get_database_context(session.sandbox_state["db_path"])

        sql_coder=SqlCoderAgent(client=client)
        sql_critic=SqlCriticAgent(client=client)
        summarizer=SummarizerAgent(client=client)
    except Exception as e:
        raise PipelineException(
            "Failed initializing database schema or agents",
            stage=PipelineStage.SCHEMA_EXTRACTION,
            is_fatal=True
        ) from e    
    
    attempts=[]

    for attempt in range(1,max_retries+1):
         attempt_start = time.perf_counter()
         logger.info("Initiating SQL pipeline cycle.", extra={"extra_data": {"attempt": attempt, "session_id": session_id}})

        # STAGE 2: Code Generation
         try:
            agent_response = sql_coder.generate_sql_query(user_query,db_schema=db_schema ,db_context=db_context,
                                                       session=session, retry_context=PromptFormatter.format_retry_attempts(attempts))

         except Exception as e:
              logger.error("Code generation failed", extra={"stage": PipelineStage.CODE_GENERATION, "error": str(e)})
              attempts.append({"code": "N/A", "status": "Generation Error", "feedback": str(e)})
              continue
         
         logger.info("Coder rationale", extra={"extra_data": {"info": agent_response.info, "session_id": session_id}})
         logger.info("Generated SQL",extra={"extra_data": {"sql": agent_response.sql_query}})

         # STAGE 3: Sandbox Execution
         result= SqlSandbox.execute(agent_response.sql_query, session.sandbox_state["db_path"])
         attempt_duration_ms = round((time.perf_counter() - attempt_start) * 1000, 2)

         if not result.success:
             logger.warning("SQL execution failed.", extra={"extra_data": {"attempt": attempt,"stage":PipelineStage.SANDBOX_EXECUTION ,"duration_ms": attempt_duration_ms, "session_id": session_id}})
             attempts.append({"code":agent_response.sql_query,"status":"Execution Error","feedback":result.error_message})
             continue

         result_text=result.result_df.to_string(index=False)
         verdict=sql_critic.evaluate_logic(query=user_query,db_schema=db_schema,db_context=db_context,sql=agent_response.sql_query,output=result_text,session=session)

         if verdict.is_correct:
             total_duration_ms=round((time.perf_counter() - pipeline_start) * 1000, 2)
             logger.info("Pipeline successful. System state approved by internal auditor.",extra={
                                     "extra_data":{"attempts_used":attempt,
                                                   "total_duration_ms":total_duration_ms,
                                                   "last_attempt_duration_ms":attempt_duration_ms,"session_id": session_id}})
             try:
                summary=summarizer.summarize(user_query=user_query,code=agent_response.sql_query,output=result_text)
                new_turn=MemoryTurn(user_query=user_query,
                                                successful_code=SqlSandbox.normalize_query(agent_response.sql_query),
                                                execution_output=result_text,summary=summary)
                memory.add_turn(session,new_turn)
                logger.info("Pipeline successful. Turn committed to session memory state store.")   
             except Exception as e:
                 logger.error("Failed persisting memory state, proceeding to return output", 
                             extra={"stage": PipelineStage.MEMORY_PERSISTENCE, "error": str(e)})    
             return result_text

         else:
             logger.warning(f"Logic failure rejected by auditor. Context loop updated.", 
                                        extra={"extra_data": {"critique": verdict.critique,"duration_ms":attempt_duration_ms,"session_id": session_id}})

             attempts.append({
                         "code": SqlSandbox.normalize_query(agent_response.sql_query),
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
    raise PipelineException(
        f"SQL Pipeline reached max retries ({max_retries}). Last feedback: {last_feedback}, Last Staus:{last_status}",
        stage=PipelineStage.SANDBOX_EXECUTION,
        is_fatal=True
    )



