from pydantic import BaseModel,Field
from google import genai
from google.genai import types
import pandas as pd
import traceback
from contextlib import redirect_stdout
import io
from dotenv import load_dotenv

load_dotenv()

client=genai.Client()

class DataTableInfo(BaseModel): 
    info:str=Field("Explanation of the aquired answer from the dataset")
    code:str=Field("Executable python code with no markdown codes or filler text")



def get_csv_schema(df:pd.DataFrame) -> str:

    """Extracts column names and missing value statistics to prompt the LLM."""
  
    # Capture structural details
    columns_and_types=df.dtypes.to_dict()
    missing_values=df.isnull().sum()

    # Format it cleanly as a text payload for the prompt
    schema_summary="Dataset Schema Information:\n"
    
    for col, dtype in columns_and_types.items():
        schema_summary+=f"- Column: {col} | Type: {dtype} | Missing Values: {missing_values[col]}\n"

    return schema_summary


if __name__ == "__main__":

    # 1. Read the csv  exactly once
    df=pd.read_csv("sales_data.csv")

    # Extracted schema input
    csv_schema=get_csv_schema(df)

    # User query

    user_query="Calculate the total revenue generated from the Electonics category,taking into account any discounts applied."

    # Prompt to the model
    prompt=f"""You are an expert data analyst agent. 
    An in-memory pandas DataFrame named 'df' has already been loaded for you. Do NOT call pd.read_csv()

    Here is the structural schema of the dataset:{csv_schema}

    Based on this schema,write a python pandas script to answer the users query.
    User Query:{user_query}"""

    response=client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DataTableInfo
        )
    )

    agent_response=DataTableInfo.model_validate_json(response.text)

    output_buffer=io.StringIO()
    try:
        # 4. CREATE A CUSTOM GLOBAL CONTEXT DICTIONARY
        # We map the string key "df" to our actual local 'df' variable.
        # We also pass 'print' so the execution scope can use it.
        sandbox_globals = {"df": df,"pd":pd}
        
        with redirect_stdout(output_buffer):
            exec(agent_response.code,sandbox_globals)
            

        print("Succesful Execution\nOutput :")
        print(output_buffer.getvalue())
        print(agent_response.code)
    except Exception as e:
        error_msg=traceback.format_exc()
        print("Execution failed! Error Traceback Captured :")
        print(error_msg)
        