from google import genai
from prompts.formatter import PromptFormatter


class SummarizerAgent():
    
    def __init__(self,client:genai.Client,model:str="gemini-3.1-flash-lite"):
        self.client=client
        self.model=model

        
    
    def summarize(self,user_query:str,code:str,output:str) -> str :

        summarizer_prompt=f"""You are an execution summarization assistant.Your job is to summarize a successful  execution
        for future Ai conversation context

        IMPORTANT RULES :
        - Maximum 2 sentences
        - Mention important variables created if obvious
        - Describe what was accomplished
        - Do not explain Python syntax
        - Keep it concise.

        {PromptFormatter.build_section("USER QUERY",user_query)}
        {PromptFormatter.build_section("GENERATED CODE",code)}
        {PromptFormatter.build_section("PROGRAM OUTPUT",output)}


        Return only the summary text.

        """

        response=self.client.models.generate_content(
            model=self.model,
            contents=summarizer_prompt,
        )

        return response.text.strip()
        
