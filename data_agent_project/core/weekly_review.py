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

logger = get_logger(__name__)


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
        for c in profile_result.columns
    }
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
    if baseline_runs is not None:
        print(f"TOTAL DFS To Concat : {len(baseline_runs)}")
        dfs=[]
        try:
            print("ENTERED HERE")
            for b_run in baseline_runs:
                b_df=load_dataframe(b_run)
                if b_df is not None and not b_df.empty:
                    dfs.append(b_df)

            if dfs:
                baseline_df = pd.concat(dfs,ignore_index=True)
                # --- QUICK DEBUG PRINT ---
                print(f"👉 DEBUG BASELINE CONCAT: Shape={baseline_df.shape}, Min Date={baseline_df['date'].min()}, Max Date={baseline_df['date'].max()}")
        except FileNotFoundError:
            logger.warning("Baseline file missing, skipping baseline comparison",
                           extra={"extra_data": {"baseline_runs_count": len(baseline_runs)}})

    # --- 3. Detect ---
    anomaly_candidates = detect_anomalies(df, profile_result, baseline_df)
    quality_candidates = detect_quality_findings(df, profile_result=profile_result)
    candidates = anomaly_candidates + quality_candidates

    # --- 4. Persist findings + birth evidence ---
    persisted_ids: list[str] = []
    current_fingerprints: set[str] = set()

    print("LEN OF CANDIDATES :",len(candidates))

    for c in candidates:
        fp = fingerprint_candidate(c)
        current_fingerprints.add(fp)


        check_name=c.birth_evidence['content'].get('check','stat')
        ev_type=_get_evidence_type(check_name)

        birth_ev=Evidence(
                        evidence_id=_new_id("ev"),
                        finding_id=None,
                        origin="tool",
                        type=ev_type, 
                        content_json=c.birth_evidence["content"],
                        result_json=c.birth_evidence["result"],
                        interpretation="Initial interpretation",
                        supports=True,
                    )
        

        existing = _find_prior_finding(db, run.source_id, fp)
        
        if existing is not None:
            
            existing.updated_at = datetime.now(timezone.utc)

            birth_ev.finding_id=existing.finding_id
            birth_ev.interpretation = f"Re-detected in run {run_id}"

            prior_evidence=db.scalars(
                                    select(Evidence).where(Evidence.finding_id == existing.finding_id)
                                ).all()

            # Combine prior evidence with the new chapter (FLAT list)
            all_evidence = prior_evidence + [birth_ev]
            
            confidence, conf_status = calculate_confidence(all_evidence)
            
            existing.status = "contradicted" if conf_status == 'contradicted' else "ongoing"
            existing.confidence = confidence

            db.add(birth_ev)

            persisted_ids.append(existing.finding_id)
            logger.info("Finding re-detected as ongoing",
                        extra={"extra_data": {"finding_id": existing.finding_id,
                                              "status": existing.status,"confidence":existing.confidence}})
        else:
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

            # The generator part before adding to db 
            generated_claim=generate_claim(candidate=c,run_date=run.run_date,source_name=run.source.name)

        
            db.add(finding)
            db.flush()
            birth_ev.finding_id=finding.finding_id
            db.add(birth_ev)

            # Compute initial confidence from birth evidence alone
            confidence, conf_status = calculate_confidence([birth_ev])
            finding.confidence = confidence
            if conf_status == "contradicted":
                finding.status = "contradicted"

            persisted_ids.append(finding.finding_id)
            logger.info("New finding created",
                        extra={"extra_data": {"finding_id": finding.finding_id,
                                              "metric": c.metric,"status": finding.status,
                                            "confidence": confidence}})
            
    # --- 5. Resolve missing findings ---
    active = db.scalars(
        select(Finding).where(
            Finding.source_id == run.source_id,
            Finding.status.in_(["new", "ongoing"]),
        )
    ).all()

    

    for f in active:
        if f.run_id == run_id:
            continue
        if f.fingerprint not in current_fingerprints:
            f.status = "resolved"
            f.updated_at = datetime.now(timezone.utc)
            logger.info("Finding resolved",
                        extra={"extra_data": {"finding_id": f.finding_id}})

    # --- 6. Finalize ---
    run.status = "analyzed"
    db.commit()

    logger.info("Weekly review complete",
                extra={"extra_data": {"run_id": run_id,
                                      "findings": len(persisted_ids)}})
    return RunSummary(run_id=run_id, findings_count=len(persisted_ids))


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

def generate_claim(candidate,run_date,source_name):
    pass