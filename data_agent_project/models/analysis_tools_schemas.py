from pydantic import BaseModel
from typing import Optional

class RawCandidate(BaseModel):
    category: str            # "anomaly"
    metric: str              # column name
    dimension: Optional[str] = None    # segment column, e.g. "region"
    dimension_value: Optional[str] = None  # segment value, e.g. "EU"
    direction: str | None = None           # "up" | "down" | "flat"
    magnitude: float         # 0.32 for 32%
    birth_evidence: dict     # {"content": {...}, "result": {...}}
    raw_context: dict        # numbers the generator will use to write the claim
