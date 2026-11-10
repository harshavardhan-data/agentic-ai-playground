from sqlalchemy import select
from sqlalchemy.orm import Session
from models.analysis import Evidence


def build_history_slice(db: Session, finding_id: str, limit: int = 5) -> list[dict]:
    rows = db.scalars(
        select(Evidence)
        .where(Evidence.finding_id == finding_id)
        .order_by(Evidence.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "run_week": ev.created_at.date().isoformat() if ev.created_at else "unknown",
            "claim": (ev.claim or "")[:100],
            "direction": ev.direction,
            "content_json": ev.content_json,
            "result_json": ev.result_json,
            "interpretation": (ev.interpretation or "")[:120],
            "verdict": ev.verdict,
            "supports": ev.supports,
        }
        for ev in rows
    ]


def _should_trigger_evidence(prev_ev, cur_direction, cur_magnitude, all_evidence) -> bool:
    if prev_ev is None:
        return True
    prev_dir = prev_ev.direction or (prev_ev.result_json or {}).get("direction")
    if prev_dir and cur_direction and prev_dir != cur_direction and cur_direction != "flat":
        return True
    prev_mag = abs((prev_ev.result_json or {}).get("magnitude") or 0)
    cur_mag = abs(cur_magnitude or 0)
    if prev_mag > 0 and abs(cur_mag - prev_mag) / prev_mag > 0.5:
        return True
    return False