from core.memory import SessionState
import pandas as pd


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
        if not attempts:
            return "No previous attempts in this task cycle."
        
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
        
