import uuid
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.logger import get_logger
from core.run_store import get_run, load_dataframe
from core.confidence_score import calculate_confidence
from core.critic_pipeline import run_critic_pipeline_new, run_critic_pipeline_existing
from models.analysis import DatasetRun, Finding, Evidence
from tools.analysis_tools import detect_anomalies, fingerprint_candidate
from tools.quality_tools import detect_quality_findings
from tools.profiler import inspect_dataframe
from tools.profile_slice import build_profile_dict, profile_for
from tools.history_slice import build_history_slice, _should_trigger_evidence
from agents.coder import GeneratorAgent
from agents.critic_agent_v2 import CriticAgent

logger = get_logger(__name__)


class RunSummary:
    def __init__(self, run_id: str, findings_count: int, skipped: bool = False):
        self.run_id = run_id
        self.findings_count = findings_count
        self.skipped = skipped

    def __repr__(self):
        return f"RunSummary(run_id={self.run_id!r}, findings_count={self.findings_count}, skipped={self.skipped})"


def run_weekly_review(db: Session, run_id: str, generator_agent:GeneratorAgent, critic_agent:CriticAgent) -> RunSummary:
    run = get_run(db, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    if run.status == "analyzed":
        return RunSummary(run_id=run_id, findings_count=0, skipped=True)

    # --- 1. Profile ---
    df = load_dataframe(run)
    profile_result = inspect_dataframe(df)
    run.schema_json = [c.model_dump(exclude_none=True) for c in profile_result.columns]
    run.stats_json = {
        c.name: {k: getattr(c, k) for k in ("min", "max", "mean", "median") if getattr(c, k) is not None}
        for c in profile_result.columns if c.dtype not in ("str", "object")
    }
    run.row_count = profile_result.row_count
    run.col_count = profile_result.col_count
    run.time_column = profile_result.time_column
    run.quality_flags = profile_result.quality_flags
    run.status = "profiled"
    db.commit()

    # --- 2. Baseline ---
    baseline_runs = db.scalars(
        select(DatasetRun).where(
            DatasetRun.source_id == run.source_id,
            DatasetRun.run_date < run.run_date,
            DatasetRun.status.in_(["profiled", "analyzed"]),
        ).order_by(DatasetRun.run_date.desc()).limit(6)
    ).all()
    dfs = []
    for b in baseline_runs:
        try:
            b_df = load_dataframe(b)
            if b_df is not None and not b_df.empty:
                dfs.append(b_df)
        except FileNotFoundError:
            logger.warning(f"Baseline file missing {b.run_id}")
    baseline_df = pd.concat(dfs, ignore_index=True) if dfs else None

    # --- 3. Detect + dedup ---
    candidates = detect_anomalies(df, profile_result, baseline_df) + \
                 detect_quality_findings(df, profile_result=profile_result)
    unique_candidates: dict = {}
    for c in candidates:
        unique_candidates[fingerprint_candidate(c)] = c

    # --- 4. Pass 1: build findings + birth evidence ---
    new_findings: list[Finding] = []
    existing_findings: list[Finding] = []
    all_findings: list[Finding] = []
    finding_map: dict[str, Finding] = {}

    for fp, c in unique_candidates.items():
        check = c.birth_evidence["content"].get("check", "stat")
        ev_type = _get_evidence_type(check)

        existing = _find_prior_finding(db, run.source_id, fp)

        if existing:
            birth_ev = Evidence(
                evidence_id=_new_id("ev"),
                finding_id=existing.finding_id,
                origin="tool",
                type=ev_type,
                content_json=c.birth_evidence["content"],
                result_json=c.birth_evidence["result"],
                claim=None,
                direction=c.direction,
                interpretation="Re-detected",
                supports=True,
            )
            existing.evidence.append(birth_ev)
            existing.current_direction = c.direction
            existing.updated_at = datetime.now(timezone.utc)
            existing_findings.append(existing)
            all_findings.append(existing)
            finding_map[existing.finding_id] = existing
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
                dimension_value=c.dimension_value,
                current_direction=c.direction,
                confidence=0.5,
                status="new",
                first_seen_run_id=run_id,
            )
            birth_ev = Evidence(
                evidence_id=_new_id("ev"),
                finding_id=finding.finding_id,
                origin="tool",
                type=ev_type,
                content_json=c.birth_evidence["content"],
                result_json=c.birth_evidence["result"],
                claim=None,
                direction=c.direction,
                interpretation="Initial detection",
                supports=True,
            )
            finding.evidence = [birth_ev]
            new_findings.append(finding)
            all_findings.append(finding)
            finding_map[finding.finding_id] = finding

    # --- 5. Batch claims for all findings ---
    claims_map: dict[str, str] = {}
    if all_findings:
        claims_map = generator_agent.generate_claims(
            all_findings, source_name=run.source.name, run_date=run.run_date
        )
    for f in all_findings:
        f.claim = claims_map.get(f.finding_id, "")
        if f.evidence:
            f.evidence[-1].claim = f.claim

    # --- 6. Build profile dict once ---
    profile_dict = build_profile_dict(run)

    # --- 7. Build history map for triggered existing findings ---
    history_map: dict[str, list[dict]] = {}
    for f in existing_findings:
        birth_ev = f.evidence[-1]
        # current-run candidate fields
        cur_direction = birth_ev.direction
        cur_magnitude = (birth_ev.result_json or {}).get("magnitude", 0)

        # prior tool evidence (exclude this run's birth_ev)
        prior = [ev for ev in f.evidence[:-1] if ev.origin == "tool"]
        prev_ev = prior[-1] if prior else None

        if _should_trigger_evidence(prev_ev, cur_direction, cur_magnitude, f.evidence):
            history_map[f.finding_id] = build_history_slice(db, f.finding_id, limit=5)
    # --- 8. Pass 2a: critic for NEW ---
    for finding in new_findings:
        profile = profile_for(finding, profile_dict)
        result = run_critic_pipeline_new(finding, df, profile, critic_agent)

        if result.verdict and not result.is_system_error:
            finding.evidence.append(_evidence_from_critic(finding, result))
        else:
            logger.warning(f"Skipping evidence append for {finding.finding_id} due to system error: {result.reason}")

        conf, conf_status = calculate_confidence(finding.evidence)
        finding.confidence = conf
        finding.status = "contradicted" if conf_status == "contradicted" else "new"
        db.add(finding)

    # --- 9. Pass 2b: critic for EXISTING (only triggered) ---
    for existing in existing_findings:
        if existing.finding_id in history_map:
            profile = profile_for(existing, profile_dict)
            result = run_critic_pipeline_existing(
                existing, df, profile, history_map[existing.finding_id], critic_agent
            )
            if result.verdict:
                existing.evidence.append(_evidence_from_critic(existing, result))

        conf, conf_status = calculate_confidence(existing.evidence)
        existing.confidence = conf
        existing.status = "contradicted" if conf_status == "contradicted" else "ongoing"
        db.add(existing)

    db.commit()

    # --- 10. Resolve missing ---
    detected_ids = {f.finding_id for f in all_findings}
    active = db.scalars(
        select(Finding).where(
            Finding.source_id == run.source_id,
            Finding.status.in_(["new", "ongoing"]),
        )
    ).all()
    for f in active:
        if f.finding_id not in detected_ids:
            f.status = "resolved"
            f.updated_at = datetime.now(timezone.utc)
            db.add(f)
    db.commit()

    run.status = "analyzed"
    db.commit()
    return RunSummary(run_id=run_id, findings_count=len(detected_ids))


# ---------------- helpers ----------------

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


def _get_evidence_type(check_name: str) -> str:
    if "comparison" in check_name:
        return "comparison"
    return "stat"


def _evidence_from_critic(finding: Finding, result) -> Evidence:
    return Evidence(
        evidence_id=_new_id("ev"),
        finding_id=finding.finding_id,
        origin="critic",
        type=result.plan.code_type if result.plan else "stat",
        content_json={
            "hypothesis": result.plan.artifact_hypothesis if result.plan else None,
            "code": result.plan.code_snippet if result.plan else None,
        },
        result_json={"execution": result.execution_result},
        claim=None,
        direction=None,
        verdict=result.verdict.verdict,
        proof=result.verdict.proof,
        interpretation=result.verdict.interpretation,
        supports=result.verdict.supports,
    )