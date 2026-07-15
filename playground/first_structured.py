from pydantic import BaseModel,Field
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client=genai.Client()

class PythonDataSchema(BaseModel):
    explanation:str= Field(description="A brief explanation of what the code does")
    code: str =Field(description="The executable Python code block.Do not include markdowns blocks like ```python.")

if __name__ == "__main__":

    response=client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents="Write a pandas script to count null values in a dataframe named 'df'",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PythonDataSchema
        ),
    )
    print(response.text)