import pandas as pd
from core.logger import get_logger
from models.analysis import Finding
from models.llm_schemas import CriticVerdict
from sandboxes.code_sandbox import CodeSandbox
from agents.critic_agent_v2 import CriticAgent

logger = get_logger(__name__)


class CriticResult:
    def __init__(self, plan=None, execution_result=None, verdict=None, failed=False, reason="",is_system_error=False):
        self.plan = plan
        self.execution_result = execution_result
        self.verdict = None if is_system_error else verdict
        self.failed = failed
        self.reason = reason
        self.is_system_error=is_system_error


def _uncertain(reason: str,is_system_error=False) -> CriticResult:
    return CriticResult(
        plan=None, execution_result=None,
        verdict=CriticVerdict(
            supports=True, verdict="uncertain",
            interpretation=f"Critic audit Inconclusive: {reason}",
            proof="", retry_hint=None,
        ),
        failed=True, reason=reason,
        is_system_error=is_system_error
    )


def _run_loop(finding, df, profile, history, critic_agent, generate_fn, judge_fn, max_retries=2):
    plan = None
    execution = None
    retry_context = None

    for attempt in range(1, max_retries + 1):
        try:
            plan = generate_fn(finding, profile, history, retry_context) \
                if history is not None else generate_fn(finding, profile, retry_context)
        except Exception as e:
            logger.warning(f"Plan gen failed (attempt {attempt}): {e}")
            return _uncertain(f"plan generation error: {e}",is_system_error=True)

        try:
            cleaned = CodeSandbox.clean_code(plan.code_snippet)
            execution = CodeSandbox.execute(cleaned, {"df": df})
        except Exception as e:
            retry_context = {"error": str(e)[:300], "failed_code": plan.code_snippet[:500]}
            continue

        if execution.success:
            break
        retry_context = {
            "error": (execution.error_message or "")[:300],
            "failed_code": plan.code_snippet[:500],
        }

    if execution is None or not execution.success:
        return _uncertain("verification code failed after retries",is_system_error=True)

    try:
        verdict = judge_fn(finding, plan, execution.result, profile, history) \
            if history is not None else judge_fn(finding, plan, execution.result, profile)
    except Exception as e:
        logger.warning(f"Judge failed: {e}")
        return _uncertain(f"judge error: {e}",is_system_error=True)

    if verdict.verdict == "uncertain" and verdict.retry_hint:
        try:
            retry_ctx = {"judge_note": verdict.retry_hint[:300]}
            plan2 = generate_fn(finding, profile, history, retry_ctx) \
                if history is not None else generate_fn(finding, profile, retry_ctx)
            cleaned2 = CodeSandbox.clean_code(plan2.code_snippet)
            exec2 = CodeSandbox.execute(cleaned2, {"df": df})
            if exec2.success:
                verdict = judge_fn(finding, plan2, exec2.result, profile, history) \
                    if history is not None else judge_fn(finding, plan2, exec2.result, profile)
                plan, execution = plan2, exec2
            else:
                logger.warning(f"Judge-hint retry execution failed: {exec2.error_message}")
        except Exception as e:
            logger.warning(f"Retry after judge-hint failed: {e}")

    return CriticResult(plan=plan, execution_result=execution.result, verdict=verdict)


def run_critic_pipeline_new(finding, df, profile, critic_agent:CriticAgent) -> CriticResult:
    return _run_loop(
        finding, df, profile, None, critic_agent,
        generate_fn=critic_agent.generate_verification_code_new,
        judge_fn=critic_agent.judge_verification_new,
    )


def run_critic_pipeline_existing(finding, df, profile, history, critic_agent:CriticAgent) -> CriticResult:
    return _run_loop(
        finding, df, profile, history, critic_agent,
        generate_fn=critic_agent.generate_verification_code_existing,
        judge_fn=critic_agent.judge_verification_existing,
    )