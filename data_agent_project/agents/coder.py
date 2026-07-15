from google import genai
from google.genai import types
from agents.models import CodeResponse
from core.logger import get_logger

logger=get_logger(__name__)

class CoderAgent:

    def __init__(self,client:genai.Client,model:str="gemini-3.1-flash-lite"):
        self.client=client
        self.model=model
        
    def generate_code(self,prompt:str) ->CodeResponse:
        logger.info("Invoking Coder Agent generation workflow.")
        response=self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CodeResponse
            )
        )

        # SDE Observability: Capture metadata without disrupting streaming flow
        logger.info("Coder generation complete.", extra={"extra_data": {"model": self.model}})
        return CodeResponse.model_validate_json(response.text)
    