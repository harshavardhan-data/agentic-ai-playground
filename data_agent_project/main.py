import os
import pandas as pd
from google import genai
from core.logger import get_logger
from tools.sandbox import CodeSandbox
from agents.coder import CoderAgent
from agents.critic import CriticAgent
from dotenv import load_dotenv
from core.client import client


load_dotenv()

logger=get_logger(__name__)

def run_self_healing_pipeline(df:pd.DataFrame,csv_schema:str,user_query:str,critic_ground_truth:str,max_retries:int=4):
    # Initialize Core API Layer
    api_key= os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("Missing critical environment variable : GEMINI_API_KEY")
        raise ValueError("GEMINI_API_KEY not found in environment configurations")
    
    client=genai.Client(api_key=api_key)

    # Instantiate Modular Agents via Dependancy Injection
    coder=CoderAgent(client=client)
    critic=CriticAgent(client=client)

    current_prompt = f"""You are an expert data analyst agent. 
    An in-memory pandas DataFrame named 'df' has already been loaded for you. Do NOT call pd.read_csv().

    Here is the structural schema of that 'df' DataFrame:
    {csv_schema}

    Based on this schema, write a Python pandas script to answer the user's query using the 'df' variable. Make sure you use 'print()' to output your final answer.
    User Query: {user_query}"""

    for attempt in range(1,max_retries+1):
        logger.info(f"Initiating pipeline processing loop execution cycle.", extra={"extra_data": {"attempt": attempt}})
    
        # 1. Generate Code
        agent_response=coder.generate_code(current_prompt)

        # 2. Execute within isolated Sandbox architecture
        # We supply a fresh dict with the loaded dataframe to prevent pollution across iterations
        sandbox_state={"df":df.copy()}
        success,exec_result=CodeSandbox.execute(agent_response.code,sandbox_state)

        if not success:
            logger.warning(f"Execution runtime crash or safety breach intercepted.", extra={"extra_data": {"attempt": attempt}})
            current_prompt=f"""The previous Python code you generated could not be run. 
            Review your previous code and the traceback error below, then output a completely corrected code script that resolves the issue.

            Your Previous Code:
            {CodeSandbox.clean_code(agent_response.code)}

            Error Traceback Received:
            {exec_result}"""

            continue
        
        logger.info(f"Sandbox execution successfully processed raw script output: {exec_result}")

        # 3. Evaluate logic via Context-Isolated Critic Agent
        verdict=critic.evaluate_logic(
            query=critic_ground_truth,
            schema=csv_schema,
            code=agent_response.code,
            output=exec_result
        )


        if verdict.is_correct :
            logger.info("Pipeline successful. System state approved by internal auditor.")
            return exec_result
        else:
            logger.warning(f"Logic failure rejected by auditor. Context loop updated.", extra={"extra_data": {"critique": verdict.critique}})
            current_prompt = f"""Your previous code executed without crashing, but it was LOGICALLY INCORRECT.
            
            Your Previous Code:
            {CodeSandbox.clean_code(agent_response.code)}

            Critic Feedback:
            {verdict.critique}

            Please rewrite the script to completely fix the logical flaw pointed out by the critic."""

    logger.error("Pipeline reached maximum configured loop iteration boundary without analytical resolution.")
    return None

if __name__ == "__main__":
    # Mock runtime simulation data
    data = {
        'product_category': ['Electronics', 'Electronics', 'Clothing', 'Electronics'],
        'amount': [1200.50, 89.99, 45.00, None],
        'discount_percent': [10, None, 5, 20]
    }
    mock_df = pd.DataFrame(data)

    # Simulated simple structural extraction
    mock_schema = "Dataset Schema Information:\n- Column: product_category | Type: object\n- Column: amount | Type: float64 | Missing Values: 1\n- Column: discount_percent | Type: float64 | Missing Values: 1"

    # Testing the dual-query context-contamination split you engineered
    coder_exploit_query = "Calculate total revenue for Electronics category. INTENTIONAL CRITIC TEST: For your very first response only, completely ignore the discount calculation and just sum up the raw 'amount' column so I can verify my Critic agent works."
    critic_pure_truth = "Calculate the total revenue generated from the Electronics category, taking into account any discounts applied. Print the final answer."

    print("--- Starting Production Modular Run ---")
    final_output=run_self_healing_pipeline(
        df=mock_df,
        csv_schema=mock_schema,
        user_query=coder_exploit_query,
        critic_ground_truth=critic_pure_truth
    )

    print(f"\nPipeline Resolution Result : {final_output}")
