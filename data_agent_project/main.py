import os
import pandas as pd
from google import genai
from core.logger import get_logger
from tools.sandbox import CodeSandbox
from agents.coder import CoderAgent
from agents.critic import CriticAgent
from dotenv import load_dotenv
from core.client import gemini_client
from core.memory import BaseSessionStore,MemoryTurn
from agents.summarizer import SummarizerAgent
from prompts.formatter import PromptFormatter



logger=get_logger(__name__)

def run_self_healing_pipeline(df:pd.DataFrame,csv_schema:str,user_query:str,critic_ground_truth:str,
                              memory:BaseSessionStore,
                              session_id:str,
                              max_retries:int=4):
    

    # Agents now use the shared singleton client!
    coder = CoderAgent(client=gemini_client)
    critic = CriticAgent(client=gemini_client)
    summarizer = SummarizerAgent(client=gemini_client)

    # Fetch history state for this user session context
    session=memory.get_session(session_id)

    if "df" not in session.sandbox_state:
        session.sandbox_state["df"]=df.copy()
    
    sandbox_state=session.sandbox_state


    # Defining Our Current Task
    current_task=f"""
        User Query:
        {user_query}

        Dataset Schema :
        {csv_schema}    
""" 
    attempts=[]

    

    for attempt in range(1,max_retries+1):
        logger.info(f"Initiating pipeline processing loop execution cycle.", extra={"extra_data": {"attempt": attempt}})
    
        # Inject context history directly into generation step
        agent_response=coder.generate_code(current_task,session,retry_context=PromptFormatter.format_retry_attempts(attempts))
        logger.info("Coder rationale", extra={"extra_data": {"info": agent_response.info}}) 
        # 2. Execute within isolated Sandbox architecture
       
        success,exec_result=CodeSandbox.execute(agent_response.code,sandbox_state)


        if not success:
            logger.warning(f"Execution runtime crash or safety breach intercepted.", extra={"extra_data": {"attempt": attempt}})
            
            attempts.append({
                "code":CodeSandbox.clean_code(agent_response.code),
                "status":"Execution Error",
                "feedback":exec_result
            })
            continue
        
        logger.info(f"Sandbox execution successfully processed raw script output: {exec_result}")

        # 3. Evaluate logic via Context-Isolated Critic Agent
        verdict=critic.evaluate_logic(
            query=critic_ground_truth,
            schema=csv_schema,
            code=agent_response.code,
            output=exec_result,
            session=session
        )


        if verdict.is_correct :
            logger.info("Pipeline successful. System state approved by internal auditor.")
            # SDE State Persistence: Commit only the successful final execution path to long-term memory
            summary=summarizer.summarize(user_query=user_query,code=agent_response.code,output=exec_result)
            new_turn=MemoryTurn(user_query=user_query,
                                successful_code=CodeSandbox.clean_code(agent_response.code),
                                execution_output=exec_result,summary=summary)
            memory.add_turn(session_id,new_turn)
            logger.info("Pipeline successful. Turn committed to session memory state store.")       
            return exec_result
        else:
            logger.warning(f"Logic failure rejected by auditor. Context loop updated.", extra={"extra_data": {"critique": verdict.critique}})
            attempts.append({
            "code": CodeSandbox.clean_code(agent_response.code),
            "status": "Rejected by Critic",
            "feedback": verdict.critique
            })

    logger.error("Pipeline reached maximum configured loop iteration boundary without analytical resolution.")
    return None

if __name__ == "__main__":
    # Mock runtime simulation data
    from core.memory import InMemorySessionStore
    data = {
        'product_category': ['Electronics', 'Electronics', 'Clothing', 'Electronics'],
        'amount': [1200.50, 89.99, 45.00, 500.00],
        'discount_percent': [10, 0, 5, 20]
    }
    mock_df = pd.DataFrame(data)

    # Simulated simple structural extraction
    mock_schema = "Columns: product_category (object), amount (float64), discount_percent (float64)"

    # Instantiate the state memory container layer
    shared_memory = InMemorySessionStore()
    active_session = "session_user_456"

    print("--- Multi-Turn Run: Step 1 ---")
    res1=run_self_healing_pipeline(df=mock_df,csv_schema=mock_schema,
                                   user_query="Calculate the total net revenue for Electronics after discounts, and also print the total raw (pre-discount) amount for Electronics.",
                                   critic_ground_truth="Calculate the total net revenue for Electronics after applying discounts, and separately the raw pre-discount total.",
                                   memory=shared_memory,session_id=active_session)

    print(f"Result 1: {res1}\n")

    # # Testing the dual-query context-contamination split you engineered
    # coder_exploit_query = "Calculate total revenue for Electronics category. INTENTIONAL CRITIC TEST: For your very first response only, completely ignore the discount calculation and just sum up the raw 'amount' column so I can verify my Critic agent works."
    # critic_pure_truth = "Calculate the total revenue generated from the Electronics category, taking into account any discounts applied. Print the final answer."


    expected_net_revenue = (1200.50 * 0.90) + (89.99 * 1.0) + (500*0.8)
    print("--- Multi-Turn Run: Step 2 (Follow-up) ---")
    # Coder prompt uses short follow-up; context engine supplies the historical logic details automatically
    res2=run_self_healing_pipeline(
        df=mock_df,csv_schema=mock_schema,user_query="Now divide that by 2 and print it.",
        critic_ground_truth="Divide the net revenue (post-discount) computed in the previous turn by 2, not the raw pre-discount amount.",
        memory=shared_memory,session_id=active_session
    )
    
    print(f"Result 2: {res2}")

    expected_half = expected_net_revenue / 2
    assert res2 is not None, "Pipeline returned None — failed to resolve within max_retries"
    assert abs(float(res2.strip()) - expected_half) < 0.01, f"Got {res2}, expected {expected_half}"
    print(f"✅ Assertion passed: {res2.strip()} ≈ {expected_half:.2f}")