from first_structured import client,PythonDataSchema
import io
from contextlib import redirect_stdout
from google.genai import types
import traceback



response=client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents="Write a pure 1-line Python snippet that prints a variable named undefined_variable. Do not include any try/except blocks or error handling.",
        config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PythonDataSchema
        )
        ,
        )

agent_object=PythonDataSchema.model_validate_json(response.text)
    
output_buffer=io.StringIO()
try:
    with redirect_stdout(output_buffer):
                        exec(agent_object.code)

    print("Output :")
    print(output_buffer.getvalue())
except Exception as e:
    error_message=traceback.format_exc()
    print("Execution Failed! Error Traceback captured:")
    print(error_message)            
                
        




