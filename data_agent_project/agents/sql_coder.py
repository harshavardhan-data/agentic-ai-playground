from google import genai
from google.genai import types
from models.llm_schemas import SqlResponse
from core.memory import SessionState
from core.logger import get_logger
from core.telemetry import log_call, log_token_usage
from prompts.formatter import PromptFormatter


logger=get_logger(__name__)




class SqlCoderAgent:

    def __init__(self,client:genai.Client,model:str="gemini-3.1-flash-lite"):
        self.client=client
        self.model=model


    @log_call
    def generate_sql_query(self,current_task:str,session:SessionState,db_schema:str,db_context,retry_context:str="") -> SqlResponse:

        history_section = PromptFormatter.format_history(session)

        current_prompt=f"""
            You are an expert SQL query generation agent.

            Important Execution Rules:
            - Generate exactly ONE executable SQL query.
            - Only generate read-only SQL (SELECT statements, WITH/CTEs are allowed).
            - Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE, PRAGMA, or other data-modifying statements.
            - Use only the tables and columns provided in the supplied schema. Never invent table or column names.
            - SQLite string comparisons using '=' can be case-sensitive.
            - When filtering TEXT columns from user input, use case-insensitive comparisons (e.g., LOWER(column) = LOWER('value')) unless the user explicitly 
              asks for an exact case-sensitive match.
            - Do not use SELECT * unless the user explicitly requests every column.
            - Use explicit JOIN syntax and qualify column names whenever ambiguity is possible.
            - Prefer the simplest correct query over unnecessarily complex solutions.
            - Respect the provided SQL dialect.
            - Return only executable SQL. Do not wrap it in markdown or include explanations.
            - Assume the generated query will be validated and executed by a separate SQL execution environment.
            - Never assume a numeric column is fully populated. Before writing any arithmetic or aggregation on a 
            numeric column, explicitly consider whether NULLs could be present and what should happen to them.
            - Aggregates (SUM/AVG/COUNT) already skip NULLs by default — that's usually fine on its own. Row-level 
            arithmetic (e.g. amount * (1 - discount/100)) does NOT protect itself — a NULL anywhere in the expression 
            poisons the whole row silently.
            - Where a default is safe — because "missing" and the default value mean the same real-world thing 
            (e.g. missing discount → 0% discount) — use COALESCE. Where defaulting would invent a fact that wasn't 
            there — because "missing" and the default value mean different things (e.g. missing price/amount → 0 
            would falsely claim the transaction was worthless) — filter with WHERE column IS NOT NULL instead, and 
            note how many rows were excluded.

            {PromptFormatter.build_section("CURRENT TASK", current_task)}


            {PromptFormatter.build_section("DATABASE SCHEMA",db_schema)}

            {PromptFormatter.build_section("DATABASE CONTEXT", PromptFormatter.format_db_context(db_context))}

       

            {PromptFormatter.build_section(
                "ATTEMPTS SO FAR THIS TASK (all failed — do not repeat these mistakes)",
                retry_context or "No previous attempts."
            )}

            {PromptFormatter.build_section("SESSION HISTORY", history_section)}

        """

        response=self.client.models.generate_content(
            model=self.model,
            contents=current_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json",response_schema=SqlResponse)
        )
        log_token_usage(response,"sql_coder")
        return SqlResponse.model_validate_json(response.text)
