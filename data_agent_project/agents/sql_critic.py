# agents/sql_critic.py
from google import genai
from google.genai import types
from models.llm_schemas import SQLCriticVerdict   # reused, unchanged — see reasoning above
from core.logger import get_logger
from core.memory import SessionState
from core.telemetry import log_call, log_token_usage
from prompts.formatter import PromptFormatter

logger = get_logger(__name__)


class SqlCriticAgent:
    def __init__(self, client: genai.Client, model: str = "gemini-3.1-flash-lite"):
        self.client = client
        self.model = model

    @log_call
    def evaluate_logic(self, query: str, db_schema: str,db_context:str, sql: str, output: str, session: SessionState) -> SQLCriticVerdict:
        history_section = PromptFormatter.format_history(session)

        critic_prompt = f"""
            You are an expert SQL reviewer.

            Your responsibility is to determine whether the generated SQL correctly satisfies the user's request.

            Evaluation Rules:
            - Verify that every referenced table and column exists in the supplied schema.
            - Ensure the query satisfies the user's intent.
            - Detect logical mistakes such as incorrect joins, filters, grouping, ordering, or aggregation.
            - Verify that text filters are robust.
            - If a query compares TEXT values using '=', consider whether case sensitivity could incorrectly exclude matching rows.
            - Detect unnecessary complexity when a simpler correct query exists.
            - Ensure the query follows the provided SQL dialect.
            - Reject any data-modifying or schema-modifying statements.
            - Ignore formatting preferences unless they affect execution.
            - Do not rewrite the query. Only evaluate it.
            - Check whether calculated/aggregated columns are NULL-safe (COALESCE or explicit IS NOT NULL). Treat 
            undefended row-level arithmetic on a nullable column as suspect, not safe by default.
            - If COALESCE is used, confirm the default fits the column's meaning — defaulting a missing amount/price 
            to 0 is wrong (it silently zeroes real values); defaulting a missing discount to 0 is fine.
            - If rows are excluded via NULL filtering, confirm that's acknowledged somewhere. Silent, unacknowledged 
            exclusion should fail the review.

            Return your verdict using the provided response schema.

            {PromptFormatter.build_section("CURRENT USER REQUEST", query)}

            {PromptFormatter.build_section("DATABASE SCHEMA", db_schema)}

            {PromptFormatter.build_section("Database Context",db_context)}

            {PromptFormatter.build_section("GENERATED SQL", sql)}

            {PromptFormatter.build_section("QUERY OUTPUT", output)}

            {PromptFormatter.build_section("SESSION HISTORY", history_section)}

    
            """

        response = self.client.models.generate_content(
            model=self.model,
            contents=critic_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=SQLCriticVerdict)
        )
        log_token_usage(response, "sql_critic")
        return SQLCriticVerdict.model_validate_json(response.text)