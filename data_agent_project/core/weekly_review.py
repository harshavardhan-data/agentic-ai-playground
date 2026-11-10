import uuid
from datetime import datetime,timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
import pandas as pd
from core.logger import get_logger
from core.run_store import get_run, load_dataframe
from core.confidence_score import calculate_confidence
from models.analysis import DatasetRun, Finding, Evidence
from models.analysis_tools_schemas import RawCandidate
from tools.analysis_tools import detect_anomalies, fingerprint_candidate
from tools.quality_tools import detect_quality_findings
from tools.profiler import inspect_dataframe
from agents.coder import GeneratorAgent
from agents.critic_agent import CriticAgent
from google import genai
from core.client import gemini_client

logger = get_logger(__name__)

generator_agent=GeneratorAgent(client=gemini_client)
critic_agent=CriticAgent(client=gemini_client)
class RunSummary:
    def __init__(self, run_id: str, findings_count: int, skipped: bool = False):
        self.run_id = run_id
        self.findings_count = findings_count
        self.skipped = skipped

    def __repr__(self):
        return (f"RunSummary(run_id={self.run_id!r}, "
                f"findings_count={self.findings_count}, skipped={self.skipped})")


def run_weekly_review(db: Session, run_id: str) -> RunSummary:
    run = get_run(db, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    if run.status == "analyzed":
        logger.info("Run already analyzed, skipping",
                    extra={"extra_data": {"run_id": run_id}})
        return RunSummary(run_id=run_id, findings_count=0, skipped=True)

    # --- 1. Profile ---
    df = load_dataframe(run)
    profile_result = inspect_dataframe(df)

    run.schema_json = [c.model_dump(exclude_none=True) for c in profile_result.columns]
    run.stats_json = {
        c.name: {k: getattr(c, k) for k in ("min", "max", "mean", "median")
                 if getattr(c, k) is not None}
        for c in profile_result.columns if c.dtype not in ("str","object") 
    }
    run.row_count=profile_result.row_count
    run.col_count=profile_result.col_count
    run.time_column = profile_result.time_column
    run.quality_flags = profile_result.quality_flags
    run.status = "profiled"
    db.commit()

    # --- 2. Baseline lookup ---
    baseline_runs = db.scalars(
        select(DatasetRun).where(
            DatasetRun.source_id == run.source_id,
            DatasetRun.run_date < run.run_date,
            DatasetRun.status.in_(["profiled", "analyzed"]),
        ).order_by(DatasetRun.run_date.desc()).limit(6)
    ).all()

    baseline_df = None
    if baseline_runs:
        print(f"TOTAL DFS To Concat : {len(baseline_runs)}")
        dfs=[]
            
            
        for b_run in baseline_runs:
            try:
                b_df=load_dataframe(b_run)
                if b_df is not None and not b_df.empty:
                    dfs.append(b_df)
            except FileNotFoundError:
                logger.warning(f"Baseline file missing {b_run.run_id}")
        if dfs:
            baseline_df = pd.concat(dfs,ignore_index=True)
                # --- QUICK DEBUG PRINT ---
            print(f"👉 DEBUG BASELINE CONCAT: Shape={baseline_df.shape}, Min Date={baseline_df['date'].min()}, Max Date={baseline_df['date'].max()}")
        
    # --- 3. Detect ---
    anomaly_candidates = detect_anomalies(df, profile_result, baseline_df)
    quality_candidates = detect_quality_findings(df, profile_result=profile_result)
    candidates = anomaly_candidates + quality_candidates

    # --- 4. Persist findings + birth evidence ---
   

    print("LEN OF CANDIDATES :",len(candidates))

    # Dedup candidates within the current run batch
    unique_candidates = {}
    for c in candidates:
        fp = fingerprint_candidate(c)
        # If the same fingerprint appears twice in this run, keep the latest
        unique_candidates[fp] = c 


    re_candidates=[]
    new_candidates=[]

    for fp,c in unique_candidates.items():
        
        existing=_find_prior_finding(db,run.source_id,fp)
        if existing:
            re_candidates.append((existing,c))
        else:
            new_candidates.append(c)


    new_findings_in_memory=[]
    finding_map={}

    for c in new_candidates:
        fp = fingerprint_candidate(c)
        
        check_name=c.birth_evidence['content'].get('check','stat')
        ev_type=_get_evidence_type(check_name)

        birth_ev=Evidence(
                        evidence_id=_new_id("ev"),
                        finding_id=None,
                        origin="tool",
                        type=ev_type, 
                        content_json=c.birth_evidence["content"],
                        result_json=c.birth_evidence["result"],
                        interpretation="Initial Detection",
                        supports=True,
                    )
        
        finding = Finding(
                finding_id=_new_id("fnd"),
                run_id=run_id,
                source_id=run.source_id,
                fingerprint=fp,
                category=c.category,
                claim="",
                metric=c.metric,
                dimension=c.dimension,
                confidence=0.5,
                status="new",
                first_seen_run_id=run_id,
            )

        
        finding.evidence=[birth_ev]

        new_findings_in_memory.append(finding)
        finding_map[finding.finding_id]=finding

        # Generator Agent Claims
    


    

    if new_findings_in_memory:

        claims_dict=generator_agent.generate_claims(new_findings_in_memory,source_name=run.source.name,run_date=run.run_date)

    # populate the claims to findings
        for f_id,claim_text in claims_dict.items():
            if f_id in finding_map:
                    finding_map[f_id].claim=claim_text
        

        # 2. Per-Finding Critic & Confidence Loop
        for finding in new_findings_in_memory:
            critic_result = critic_agent.audit_finding(finding)
        
            critic_ev = Evidence(
            evidence_id=_new_id("ev"),
            finding_id=finding.finding_id,
            origin="critic",
            type=critic_result["type"],
            supports=(critic_result['verdict'] == 'supports'),
            interpretation=critic_result['interpretation'],
            proof=critic_result["proof"],
            verdict=critic_result['verdict'],
        )
            finding.evidence.append(critic_ev)
            
            # Deterministic confidence
            conf, verdict = calculate_confidence(finding.evidence)
            finding.confidence = conf
            finding.status = "contradicted" if verdict == "contradicted" else "new"

            db.add(finding) # Stages finding + cascades evidence records cleanly

        
    


    ## Handling the Existing Candidates
    # ====================================
    detected_finding_ids = set(finding_map.keys())
    for existing,candidate in re_candidates:

        existing.updated_at=datetime.now(timezone.utc)
        existing.status="ongoing"
        check_name=candidate.birth_evidence['content'].get('check','stat')
        
        new_ev=Evidence(evidence_id=_new_id("ev"),
                finding_id=existing.finding_id,
                origin="tool",
                type=_get_evidence_type(check_name), 
                content_json=candidate.birth_evidence["content"],
                result_json=candidate.birth_evidence["result"],
                interpretation="Re Detected the Finding",
                supports=True,

                )


        existing.evidence.append(new_ev)

        conf,verdict=calculate_confidence(existing.evidence)

        existing.confidence=conf
        existing.status = (
                "contradicted" if verdict == "contradicted" else "ongoing"
            )
        detected_finding_ids.add(existing.finding_id)
        db.add(existing)
    
    db.commit()    

            
    # --- 5. Resolve missing findings ---
    active_prior_findings = db.scalars(
        select(Finding).where(
            Finding.source_id == run.source_id,
            Finding.status.in_(["new", "ongoing"]),
        )
    ).all()

    

    for prior_finding in active_prior_findings:
        if prior_finding.finding_id not in detected_finding_ids:
            prior_finding.status = "resolved"
            prior_finding.updated_at = datetime.now(timezone.utc)
            logger.info("Finding resolved",
                        extra={"extra_data": {"finding_id": prior_finding.finding_id}})
            db.merge(prior_finding)


    db.commit()

    # --- 6. Finalize ---
    run.status = "analyzed"
    db.commit()

    logger.info("Weekly review complete",
                extra={"extra_data": {"run_id": run_id,
                                      "findings": len(detected_finding_ids)}})
    return RunSummary(run_id=run_id, findings_count=len(detected_finding_ids))


def _find_prior_finding(db: Session, source_id: str, fingerprint: str):
    return db.scalars(
        select(Finding).where(
            Finding.source_id == source_id,
            Finding.fingerprint == fingerprint,
            Finding.status.in_(["new", "ongoing"]),
        ).order_by(Finding.created_at.desc())
    ).first()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _get_evidence_type(check_name:str) -> str :
    if "comparison" in check_name:
        return "comparison"
    elif "quality" in check_name:
        return "stat"
    else:
        return "stat"


def build_critic_context(finding:Finding,run:DatasetRun) -> dict:

    schema_json=run.schema_json or []
    stats_json=run.stats_json or {}

    
    schema_map={c['name']:c for c in schema_json}

    # Row count and time column
    row_count=run.row_count 
    time_column=run.time_column


    target_col=finding.metric
    

    target_profile={}

    if target_col in schema_map:
        t_meta = schema_map[target_col]
        target_profile.update({
            "dtype":t_meta.get("dtype"),
            "null_pct":t_meta.get("null_pct","Not identified")
        })
    if target_col in stats_json:
        target_profile['stats']=stats_json[target_col]

    # 3. Specific Dimension Profile
    dim_profile={}

    if finding.dimension and finding.dimension in schema_map:
        d_meta=schema_map[finding.dimension]

        dim_profile={
            "dtype": d_meta.get("dtype"),
            "null_pct": d_meta.get("null_pct", 0.0),
            "unique_count": d_meta.get("unique_count"),
            "top_5_values_with_counts": d_meta.get("top_values", {})
        } 

    # Global Anomaly 
    candidate_dims=None
    if not finding.dimension:
        
        candidates=[]
       # Filter for string/object categorical columns with low-to-medium cardinality
        filtered_categorical_cols = [
            c for c in schema_json 
            if c.get("dtype") in ("str", "object", "category") 
            and c.get("unique_count") is not None 
            and 2 <= c.get("unique_count") <= 20
        ]

        null_filtered_candidates = [
            c for c in filtered_categorical_cols 
            if c.get("null_pct", 0.0) < 0.40
        ]

        candidates = [
            {
                "name": c["name"],
                "unique_count": c["unique_count"],
                "null_pct": c["null_pct"]
            } 
            for c in null_filtered_candidates
        ]

        # Sort by lowest null percentage and take top 3
        candidates = sorted(candidates, key=lambda x: x["null_pct"])[:3]
        candidate_dims = candidates if candidates else None
       



    # Overall Null check
    nulls_summary=0.0
    total_cells=row_count*run.col_count
    total_null_cells = sum(
            c.get('null_count',0.0)  for c in schema_json
        )
    nulls_summary = float(total_null_cells / total_cells) if total_cells > 0 else 0.0

    return {
        "row_count": row_count,
        "time_column": time_column,
        f"target:{target_col}": target_profile,
        "dimension": dim_profile,
        "candidate_dims": candidate_dims,
        "nulls_summary": nulls_summary
    }  


        






    