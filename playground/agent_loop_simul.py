from pydantic import BaseModel,Field
from contextlib import redirect_stdout
import io
from google import genai
from google.genai import types
from data_input_simul import get_csv_schema,client,DataTableInfo
import traceback
import pandas as pd


# Define your maximum allowed healing attempts 
MAX_RETRIES=3

# The dataset 
df=pd.read_csv("sales_data.csv")

# User Query
user_query="""Calculate total revenue for Electronics. 
INTENTIONAL TEST: For your very first response only, intentionally reference an undefined variable named 'broken_var' 
so I can test my error healing loop."""

csv_schema=get_csv_schema(df)
# Define your current prompt
current_prompt=f"""You are an expert data analyst agent. 
An in-memory pandas DataFrame named 'df' has already been loaded for you. Do NOT call pd.read_csv().

Here is the structural schema of that 'df' DataFrame:
{csv_schema}

Based on this schema, write a Python pandas script to answer the user's query using the 'df' variable. Make sure you use 'print()' to output your final answer.
User Query: {user_query}"""


# Track execution success
success=False

for attempt in range(1,MAX_RETRIES + 1):
    print(f"\n--- Attempt {attempt} ---")

    agent_response=client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=current_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DataTableInfo
        ),
    )

    output_buffer=io.StringIO()
    agent_object=DataTableInfo.model_validate_json(agent_response.text)
    print(f"Generated Code:\n{agent_object.code}")

    # 2 . Try to run it in the sandbox
    try:
        with redirect_stdout(output_buffer):
            exec(agent_object.code,{"df":df,"pd":pd})
        
        # If it reaches here without throwing an exception, it worked!
        success = True
        print("\n✅ Execution Successful! Final Output:")
        print(output_buffer.getvalue())
        break  # Exit the retry loop entirely
    except Exception as e:
        error_msg=traceback.format_exc()
        print(f"\n❌ Execution Failed on attempt {attempt}!")

        # 3. FEEDBACK MECHANISM: Rewrite the prompt for the next loop iteration
        current_prompt=f"""The previous python code you generated failed with an error.
        Review your previous code and the traceback error below,then output a completely corrected code script that resolves
        the issue

        Your Previous Code:{agent_object.code}

        Error Traceback Received:
        {error_msg}

        Remember: You have access to an in-memory DataFrame named 'df'. Do NOT use markdown tags or reload the file"""

if not success:
    print(f"\n🚨 Agent failed to heal itself after {MAX_RETRIES} attempts.")