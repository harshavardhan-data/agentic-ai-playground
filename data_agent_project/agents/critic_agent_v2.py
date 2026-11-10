import json
from google import genai
from google.genai import types
from core.logger import get_logger
from models.analysis import Finding
from models.llm_schemas import VerificationPlan, CriticVerdict
from prompts.formatter import format_history, format_profile

logger = get_logger(__name__)


class CriticAgent:
    def __init__(self, client: genai.Client, model: str = "gemini-3.1-flash-lite"):
        self.client = client
        self.model = model

    # ---------------- NEW findings ----------------

    def generate_verification_code_new(self, finding: Finding, profile: dict,
                                       retry_context: dict | None = None) -> VerificationPlan:
        prompt = f"""You are an adversarial data auditor. Name ONE specific data artifact
        that could make this finding fake, and write Python code that would detect it.

        Rules:
        - Use only the DataFrame `df` already in scope. Do NOT reload data.
        - Output valid executable Python. Store result in variable `result`.
        - Print a short dict describing what you found.
        - One artifact hypothesis only. Be specific to this metric/dimension.

        CLAIM: "{finding.claim}"
        METRIC: {finding.metric} | DIMENSION: {finding.dimension} | VALUE: {finding.dimension_value}
        CATEGORY: {finding.category}

        PROFILE:
        {format_profile(profile)}

        RETRY CONTEXT:
        {json.dumps(retry_context) if retry_context else "none"}

        Return JSON: {{artifact_hypothesis, code_type: "python", code_snippet}}.
        """
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VerificationPlan,
            ),
        )
        return VerificationPlan.model_validate_json(response.text)

    def judge_verification_new(self, finding: Finding, plan: VerificationPlan,
                               execution_result, profile: dict) -> CriticVerdict:
        prompt = f"""You are an elite data artifact reviewer.

        Decide whether the finding's claim is trustworthy given:
        1. The verification code that was run
        2. The actual output of that code (read carefully)
        3. The data profile

        CLAIM: "{finding.claim}"
        METRIC: {finding.metric} | DIMENSION: {finding.dimension} | VALUE: {finding.dimension_value}

        PROFILE:
        {format_profile(profile)}

        VERIFICATION PLAN:
        - Hypothesis: {plan.artifact_hypothesis}
        - Code: {plan.code_snippet}

        EXECUTION OUTPUT:
        {execution_result}

        Return JSON: {{supports, verdict, interpretation, proof, retry_hint}}.
        - verdict in [contradicted, supports, uncertain]
        - supports must be consistent with verdict
        - retry_hint only if verdict=uncertain AND a different verification would help
        """
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CriticVerdict,
            ),
        )
        return CriticVerdict.model_validate_json(response.text)

    # ---------------- EXISTING findings ----------------

    def generate_verification_code_existing(self, finding: Finding, profile: dict,
                                            history: list[dict],
                                            retry_context: dict | None = None) -> VerificationPlan:
        prompt = f"""You are an adversarial data auditor reviewing a RE-DETECTED finding.

        This finding has appeared before. Your job is to determine whether this re-detection is:
        (a) a data artifact (nulls, dupes, outliers, baseline shift), OR
        (b) a real regime change / reversal versus prior weeks, OR
        (c) consistent with prior evidence.

        Use the HISTORY to understand what the finding looked like in prior weeks. Write Python
        code that would reveal the artifact OR confirm the reversal is real.

        Rules:
        - Use only the DataFrame `df` already in scope. Do NOT reload data.
        - Output valid executable Python. Store result in variable `result`.
        - Print a short dict describing what you found.
        - One hypothesis only.

        CLAIM: "{finding.claim}"
        METRIC: {finding.metric} | DIMENSION: {finding.dimension} | VALUE: {finding.dimension_value}
        CATEGORY: {finding.category}

        PROFILE:
        {format_profile(profile)}

        HISTORY (prior weeks for this finding):
        {format_history(history)}

        RETRY CONTEXT:
        {json.dumps(retry_context) if retry_context else "none"}

        Return JSON: {{artifact_hypothesis, code_type: "python", code_snippet}}.
        """
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VerificationPlan,
            ),
        )
        return VerificationPlan.model_validate_json(response.text)

    def judge_verification_existing(self, finding: Finding, plan: VerificationPlan,
                                    execution_result, profile: dict,
                                    history: list[dict]) -> CriticVerdict:
        prompt = f"""You are an elite data artifact reviewer auditing a RE-DETECTED finding.

        Decide whether the re-detection is trustworthy given:
        1. The verification code that was run
        2. The actual output of that code
        3. The data profile
        4. The HISTORY of prior weeks' claims, directions, and verdicts

        CLAIM: "{finding.claim}"
        METRIC: {finding.metric} | DIMENSION: {finding.dimension} | VALUE: {finding.dimension_value}

        PROFILE:
        {format_profile(profile)}

        HISTORY (prior weeks):
        {format_history(history)}

        VERIFICATION PLAN:
        - Hypothesis: {plan.artifact_hypothesis}
        - Code: {plan.code_snippet}

        EXECUTION OUTPUT:
        {execution_result}

        Return JSON: {{supports, verdict, interpretation, proof, retry_hint}}.
        - If history shows consistent prior verdicts, be consistent unless this result demands otherwise.
        - If the direction reversed vs history and the result confirms data integrity, say so.
        - verdict in [contradicted, supports, uncertain]
        """
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CriticVerdict,
            ),
        )
        return CriticVerdict.model_validate_json(response.text)