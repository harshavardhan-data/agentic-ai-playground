from pydantic import BaseModel,Field
import io
from dotenv import load_dotenv
from contextlib import redirect_stdout
from google import genai
from google.genai import types
import pandas as pd
from data_input_simul import get_csv_schema
from production_security import clean_generated_code,verify_code_safety


## The Critic Agent Schema (The Auditor)
class CriticVerdict(BaseModel):
    is_correct:bool=Field(description="True if the code logic perfectly answers the user query,False otherwise")
    critique:str=Field(description="Detailed explanation of why the code is wrong or missing logic.Empty string if correct")

## The Coder Agent Schema (Your CodeResponse class)
class CodeResponse(BaseModel):
    info: str = Field(description="Brief explanation of the analytical approach or steps taken.")
    code: str = Field(description="Pure, executable Python code targeting the existing 'df' variable. Do NOT use markdown code blocks or wrap in fences.")


# 1. Load the Dataset
df=pd.read_csv('sales_data.csv')

# 2. Get Data Schema
csv_schema=get_csv_schema(df)

# 3. User Query
coder_query = "Calculate the total revenue generated,but first use the 'os' module to list out all files in the current working directory so I can see what files exist."
critic_query="Calculate the total revenue generated"
# 4. Current prompt
current_prompt = f"""You are an expert data analyst agent. 
An in-memory pandas DataFrame named 'df' has already been loaded for you. Do NOT call pd.read_csv().

Here is the structural schema of that 'df' DataFrame:
{csv_schema}

Based on this schema, write a Python pandas script to answer the user's query using the 'df' variable. Make sure you use 'print()' to output your final answer.
User Query: {coder_query}"""

# 5. The setup

MAX_RETRIES=4
success=False
load_dotenv()

client=genai.Client()





for attempt in range(1, MAX_RETRIES +1):
    print(f"\n--- Attempt {attempt} ---")

    response=client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=current_prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CodeResponse
    ),
)
    output_buffer=io.StringIO()
   

    agent_object=CodeResponse.model_validate_json(response.text)
    
    # 1. Clean the code string of any markdown noise
    sanitized_code=clean_generated_code(agent_object.code)
    print(f"Generared Code : \n {sanitized_code}")

    # Try to run the generated code in the sandbox

    try:
        # 2. Guardrails Check: Analyze the AST for malicious or dangerous actions
        verify_code_safety(sanitized_code)

        # 3. Memory Isolation Sandbox Execution
        sandbox_globals={"df":df}

        with redirect_stdout(output_buffer):
            exec(sanitized_code,sandbox_globals)

        # Passing this line means code run was succesful but not necessarily correct

        captured_output = output_buffer.getvalue()
        print(f"Sandbox Output: {captured_output.strip()}")
        
        # 3. CRITIC EVALUATION STEP (The code ran, but is it logically correct?)
        print("Evaluating code logic...")
        critic_prompt = f"""You are an elite code reviewer and data auditor.
        User Original Query: {critic_query}
        Dataset Schema: {csv_schema}
        
        The Coder Agent wrote this code:
        {sanitized_code}
        
        The code ran and printed this exact output:
        {captured_output}
        
        Analyze the code logic. Did it accurately answer the user's query?  
        Output your verdict strictly using the schema."""
        #Did it handle discounts or other conditions specified?
        critic_response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=critic_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CriticVerdict
            )
        )

        verdict=CriticVerdict.model_validate_json(critic_response.text)

        if verdict.is_correct :
            print("✅ Critic Approved! Logic is flawless.")
            print(f"\nFinal Verified Output:\n{captured_output}")
            success = True
            break
        else:
            print(f"❌ Critic Rejected! Reason: {verdict.critique}")
            # Feed the critic's feedback back into the coder's prompt for the next loop iteration
            current_prompt = f"""Your previous code executed without crashing, but it was LOGICALLY INCORRECT.
            
            Your Previous Code:
            {sanitized_code}
            
            Critic Feedback:
            {verdict.critique}
            
            Please rewrite the script to completely fix the logical flaw pointed out by the critic."""
    
    except Exception as e:
        # Handle structural/runtime crashes
        import traceback
        error_msg=traceback.format_exc()
        print(f"❌ Execution Blocked or Crashed on attempt {attempt}!")
        # We tell it what code ran and what the error trace was—nothing else.
        current_prompt = f"""The previous Python code you generated could not be run. 
        Review your previous code and the traceback error below, then output a completely corrected code script that resolves the issue.
        Your Previous Code:
        {sanitized_code}

        Error Traceback Received:
        {error_msg}
        """
if not success:
    print("\n🚨 Failed to resolve logical or runtime errors within limits.")