from google import genai
from models.analysis import Finding
from models.llm_schemas import VerificationPlan,CriticVerdict
from google.genai import types
from tools.profiler import DataProfileResult
from sandboxes.code_sandbox import CodeSandbox
import pandas as pd
from prompts.formatter import format_history,format_profile
from core.logger import get_logger

logger=get_logger(__name__)

class CriticAgent:
    def __init__(self,client:genai.Client,model='gemini-3.1-flash-lite'):
        self.client=client
        self.model=model




    def generate_verification_code(self,finding:Finding,profile:dict,history:list[dict]|None=None,retry_context:dict|None=None)->VerificationPlan:

        column_profiles=""
        # finding.run.

        metric=finding.metric
        dimension=finding.dimension
        

        evidence_trail = "\n".join([
                        f"- [Origin: {ev.origin}] Type: {ev.type} | Content : {ev.content_json} | Result: {ev.result_json} | Interpretation: {ev.interpretation}"
                        for ev in finding.evidence[:5]
                    ])

        current_prompt=f"""
                    System: You are a strict adversarial data auditor and skeptical data scientist. Your job is to try to DISPROVE or CHALLENGE the given claim 
                    using its evidence history. Look for data gaps, sample size artifacts, weekend/seasonal noise, or potential false positives.
                    Be rigorous and unsparing.
        
                    Rules & Guardrails:
                    1. **Presumption of Guilt:** Treat the finding as a potential false positive until proven otherwise by the data.
                    2. **Evidence Check:** Scrutinize the historical evidence chapters. Does the trend hold up, or is it a one-off fluctuation?
                    3. **No Hallucinated Code:** In your 'interpretation' field, explain your reasoning clearly without referencing tools or code that weren't run.
                    Explain why you took an approach and what exact information took it there
                    4. Assume the necessary dataframe or other data is available to you in the current environment for direct use,dont try to reload.
                    5. Dont try to match the provided numbers and call it a success blindly,you have to produce a unbiased verification from scratch.
                    
                    Target Finding:
                    - ID: {finding.finding_id}
                    - Metric: {finding.metric}   |  Dimension: {finding.dimension}  |  Value {finding.dimension_value} | Claim: "{finding.claim}"
                    - Category :{finding.category} 
                    
                    Evidence History for this Finding:
                    {evidence_trail}

                    Current Data Profile:


                    Retry Context:
                    {retry_context if retry_context else "Nothing"}
        
                    Output Format:
                    Return a JSON object matching the requested schema with your strict audit verdict. 
        
        """
        verification_response=self.client.models.generate_content(
            model=self.model,
            contents=current_prompt,
            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=VerificationPlan
                            )
                    )

        return VerificationPlan.model_dump(verification_response.text)



    def judge_verfication(self,finding:Finding,plan:VerificationPlan,execution_result) ->CriticVerdict:

        evidence_trail = "\n".join([
                        f"- [Origin: {ev.origin}] Type: {ev.type} | Content : {ev.content_json} | Result: {ev.result_json} | Interpretation: {ev.interpretation}"
                        for ev in finding.evidence
                    ])
        
        current_prompt=f"""
        You are an Elite Data Artifact Reviewer,Verify if the given explanation and the code generated based on it are the fitting conclusion and
        evidence for the given Finding's claim ,data and past information and if its correctly supporting/contradicting it.

        Target Finding:
        - ID: {finding.finding_id}
        - Metric: {finding.metric}   |  Dimension: {finding.dimension} |  Claim: "{finding.claim}"
                            
        Evidence History:
        {evidence_trail}

        Current Data Profile:

        VERIFICATION DETAILS :
        Generated Code : {plan.code_snippet}
        Hypothesis and its Origin : {plan.artifact_hypothesis}        

        """

        judge_response=self.client.models.generate_content(
            model=self.model,
            contents=current_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CriticVerdict
            )
        )

        return CriticVerdict.model_dump(judge_response.text)


    

    def audit_finding(self,finding:Finding,df:pd.DataFrame,data_profile:DataProfileResult,retry_context=None,existing_memory=None):


        profile_info=finding.run.schema_json
        profile_info1=finding.run.stats_json

        attempts=[]

        try:
        # Format history for prompt
            evidence_trail = "\n".join([
                f"- [Origin: {ev.origin}] Type: {ev.type} | Content : {ev.content_json} | Result: {ev.result_json} | Interpretation: {ev.interpretation}"
                for ev in finding.evidence
            ])

            current_prompt=f"""
            System: You are a strict adversarial data auditor and skeptical data scientist. Your job is to try to DISPROVE or CHALLENGE the given claim using its evidence history. Look for data gaps, sample size artifacts, weekend/seasonal noise, or potential false positives. Be rigorous and unsparing.

            Rules & Guardrails:
            1. **Presumption of Guilt:** Treat the finding as a potential false positive until proven otherwise by the data.
            2. **Evidence Check:** Scrutinize the historical evidence chapters. Does the trend hold up, or is it a one-off fluctuation?
            3. **Verdict Criteria:**
            - "supports": The data robustly backs the claim.
            - "contradicted": The data disproves the claim or shows it's a false positive/artifact.
            - "uncertain": Data is inconclusive or mixed.
            4. **No Hallucinated Code:** In your 'proof' field, explain your reasoning clearly without referencing tools or code that weren't run.
            5. Assume the necessary dataframe or other data is available to you in the current environment for direct use in code.
            6. Dont try to match the provided numbers and call it a success blindly,you have to produce a unbiased verification from scratch.
            Target Finding:
            - ID: {finding.finding_id}
            - Metric: {finding.metric}   |  Dimension: {finding.dimension}  |  Claim: "{finding.claim}"
            
            Evidence History:
            {evidence_trail}

            Current Data Profile :
            {profile_info}
            {profile_info1}

            Current Run Errors:
            {"cal" if retry_context else "Nothing"}

            Output Format:
            Return a JSON object matching the requested schema with your strict audit verdict.


"""
            response = self.client.models.generate_content(
                model=self.model,
                contents=current_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    
                )
            )

            # Validate via Pydantic model
            # parsed_response = CriticResponse.model_validate_json(response.text)



            # return parsed_response.model_dump()
        except Exception as e:
            logger.warning(f"Critic Agent failed for finding {finding.finding_id} ({str(e)}). Applying safe fallback verdict.")
            
            # Safe Fallback Dictionary (Defaults to neutral support so pipeline doesn't crash)
            return {
                "supports": True,
                "type": "stat",
                "proof": f"Critic execution skipped due to system error ({str(e)}). Defaulting to baseline trust.",
                "verdict": "uncertain",
                "interpretation": "Critic Failed to Audit."
            }
