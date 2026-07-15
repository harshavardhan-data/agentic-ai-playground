from pydantic import BaseModel,Field
import io
from dotenv import load_dotenv
from contextlib import redirect_stdout
from google import genai
from google.genai import types
import pandas as pd
from data_input_simul import get_csv_schema


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
user_query = "Calculate the total revenue generated from the Electronics category, taking into account any discounts applied. Print the final answer."
user_query_1 = "Calculate the total revenue generated from the Electronics category, taking into account any discounts applied. Print the final answer. INTENTIONAL CRITIC TEST: For your very first response only, completely ignore the discount calculation and just sum up the raw 'amount' column so I can verify my Critic agent works."
# 4. Current prompt
current_prompt = f"""You are an expert data analyst agent. 
An in-memory pandas DataFrame named 'df' has already been loaded for you. Do NOT call pd.read_csv().

Here is the structural schema of that 'df' DataFrame:
{csv_schema}

Based on this schema, write a Python pandas script to answer the user's query using the 'df' variable. Make sure you use 'print()' to output your final answer.
User Query: {user_query_1}"""

# 5. The setup

MAX_RETRIES=3
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
    sandbox_globals={"df":df}

    agent_object=CodeResponse.model_validate_json(response.text)
    print(f"Generared Code : \n {agent_object.code}")

    # Try to run the generated code in the sandbox

    try:
        with redirect_stdout(output_buffer):
            exec(agent_object.code,sandbox_globals)

        # Passing this line means code run was succesful but not necessarily correct

        captured_output = output_buffer.getvalue()
        print(f"Sandbox Output: {captured_output.strip()}")
        
        # 3. CRITIC EVALUATION STEP (The code ran, but is it logically correct?)
        print("Evaluating code logic...")
        critic_prompt = f"""You are an elite code reviewer and data auditor.
        User Original Query: {user_query}
        Dataset Schema: {csv_schema}
        
        The Coder Agent wrote this code:
        {agent_object.code}
        
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
            {agent_object.code}
            
            Critic Feedback:
            {verdict.critique}
            
            Please rewrite the script to completely fix the logical flaw pointed out by the critic."""
    
    except Exception as e:
        # Handle structural/runtime crashes
        import traceback
        error_msg=traceback.format_exc()
        print(f"❌ Runtime Crash on attempt {attempt}!")
        current_prompt=f"Your code crashed:\n{error_msg}\nFix the runtime error."

if not success:
    print("\n🚨 Failed to resolve logical or runtime errors within limits.")