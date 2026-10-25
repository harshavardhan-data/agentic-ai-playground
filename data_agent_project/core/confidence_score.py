BASE_CONFIDENCE = 0.5

SUPPORT_WEIGHTS = {
    "sql": 0.15,
    "stat": 0.15,
    "python": 0.10,
    "comparison": 0.10,
}

CONTRADICT_WEIGHTS = {
    "counter": 0.30,
    "sql": 0.30,
    "stat": 0.25,
}

CONTRADICTED_THRESHOLD = 0.3


def calculate_confidence(evidence_list) -> tuple[float, str]:
    if not evidence_list:
        return (0.3, "contradicted")

    score = BASE_CONFIDENCE

    for ev in evidence_list:
        if ev.supports:
            score += SUPPORT_WEIGHTS.get(ev.type, 0.0)
        else:
            score -= CONTRADICT_WEIGHTS.get(ev.type, 0.0)

    score = max(0.0, min(1.0, score))
    status = "contradicted" if score < CONTRADICTED_THRESHOLD else "active"

    return (score, status)