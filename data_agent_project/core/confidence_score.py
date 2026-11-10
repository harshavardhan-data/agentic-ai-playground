BASE_CONFIDENCE = 0.5
CONTRADICTED_THRESHOLD = 0.35

CRITIC_WEIGHTS = {"supports": +0.20, "contradicted": -0.45, "uncertain": -0.05}
TOOL_SUPPORT_WEIGHT = 0.05
TOOL_CONTRADICT_WEIGHT = -0.20


def calculate_confidence(evidence_list) -> tuple[float, str]:
    if not evidence_list:
        return (0.5, "active")

    score = BASE_CONFIDENCE

    for ev in evidence_list:
        if ev.origin == "critic":
            score += CRITIC_WEIGHTS.get(ev.verdict, 0.0)
        elif ev.origin == "tool":
            score += TOOL_SUPPORT_WEIGHT if ev.supports else TOOL_CONTRADICT_WEIGHT
        # other origins (investigation/user) inherit no weight for now

    score = round(max(0.0, min(1.0, score)), 2)
    status = "contradicted" if score < CONTRADICTED_THRESHOLD else "active"
    return (score, status)