from core.memory import SessionState
import pandas as pd
from models.db_context import DatabaseContext
from models.analysis import Finding,Evidence


class PromptFormatter:

    @ staticmethod
    def build_section(title: str, content: str) -> str:
        return f"""
    ==================================================
    {title}
    ==================================================
    {content}
    """

    @staticmethod
    def format_history(session:SessionState) -> str:
        history=session.history

        if not history:
            return "No previous successful session history."

        context_string = ""

        for idx,turn in enumerate(history,1):
            context_string+=f"""
                    --- Past Turn {idx} ---
                    User Query: {turn.user_query}
                    Successful Code :
                    {turn.successful_code}
                    Execution Output: 
                    {turn.execution_output}
                    """
        return context_string
    
    @staticmethod
    def format_sandbox(session:SessionState) -> str:

        sandbox=session.sandbox_state

        if not sandbox:
            return "No execution state available."
        
        sandbox_text = ""

        for name, value in sandbox.items():

            if isinstance(value, pd.DataFrame):
                sandbox_text += (
                    f"{name} : DataFrame "
                    f"({value.shape[0]} rows × {value.shape[1]} columns)\n"
                )

            elif isinstance(value, pd.Series):
                sandbox_text += (
                    f"{name} : Series ({len(value)} rows)\n"
                )

            elif isinstance(value, (int, float, str, bool)):
                sandbox_text += (
                    f"{name} : {type(value).__name__}\n"
                )

            elif isinstance(value, dict):
                sandbox_text += (
                    f"{name} : dict ({len(value)} keys)\n"
                )

            elif isinstance(value, list):
                sandbox_text += (
                    f"{name} : list ({len(value)} items)\n"
                )

            else:
                sandbox_text += (
                    f"{name} : {type(value).__name__}\n"
                )

        return sandbox_text
        
    
    @staticmethod
    def format_retry_attempts(attempts:list[dict]) -> str:
        """
        'attempts' is a list of dicts like:
        {"code": "...", "status": "execution_error", "feedback": "..."}
        This turns that list into readable text the coder can react to.
        """
        if not attempts:
            return "No previous attempts in this task cycle."
        text=""
        for idx,attempt in enumerate(attempts,1):
            text+=f"""
            ------- Attempt {idx} Failed ---------
            Code generated :
            {attempt['code']}

            Failure type: {attempt['status']}
            Feedback :
            {attempt['feedback']}
            """
        return text

    @staticmethod
    def format_db_context(context:DatabaseContext) -> str:
        views_str = "\n".join(f"- {v}" for v in context.views) if context.views else "None"
        temp_str = "\n".join(f"- {t}" for t in context.temporary_tables) if context.temporary_tables else "None"
        return f"""SQL Dialect: {context.dialect}
        Database: {context.database_name}
        Execution Mode: {context.execution_mode}
        Available Views:
        {views_str}
        Temporary Tables:
        {temp_str}
        Maximum Rows Returned: {context.max_rows}"""
        



def format_findings(findings: list[Finding]) -> str:
    parts = []
    for idx, f in enumerate(findings):
        latest = f.evidence[-1] if f.evidence else None
        result = latest.result_json if latest else {}
        direction = (latest.direction if latest and latest.direction else
                     result.get("direction", "changed"))
        parts.append(
            f"=== FINDING {idx} ===\n"
            f"finding_id: {f.finding_id}\n"
            f"category: {f.category}\n"
            f"metric: {f.metric}\n"
            f"dimension: {f.dimension}\n"
            f"dimension_value: {f.dimension_value}\n"
            f"direction: {direction}\n"
            f"result_json: {result}\n"
        )
    return "\n".join(parts)


def format_history(history: list[dict]) -> str:
    if not history:
        return "No prior evidence for this finding."
    lines = []
    for h in history:
        lines.append(
            f"- week {h['run_week']} | direction: {h['direction']} | claim: \"{h['claim']}\" "
            f"| verdict: {h['verdict']} | result: {h['result_json']} "
            f"| interpretation: {h['interpretation']}"
        )
    return "\n".join(lines)


def format_profile(profile: dict) -> str:
    return (
        f"row_count: {profile.get('row_count')}\n"
        f"time_column: {profile.get('time_column')}\n"
        f"target: {profile.get('target')}\n"
        f"dimension: {profile.get('dimension')}\n"
        f"candidate_dims: {profile.get('candidate_dims')}\n"
        f"nulls_summary: {profile.get('nulls_summary')}"
    )