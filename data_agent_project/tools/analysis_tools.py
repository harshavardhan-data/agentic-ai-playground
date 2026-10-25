from tools.registry import registry
from typing import Any
from sql_main import run_sql_healing_pipeline
from main import run_self_healing_pipeline
from models.tool_context import ToolContext
from models.tool_input_schemas import AnalysisToolInput
import pandas as pd



# @registry.register(scope="sql",input_schema=AnalysisToolInput)
# def run_sql_analysis(user_query:str,__context:ToolContext) -> Any:
#     """
#     Execute the SQL analysis pipeline for the user's request.

#     user_query:
#         The user's original natural-language analytical request.
#         Pass it as the request itself, not as generated SQL.
#         The SQL specialist is responsible for generating SQL.
#     """
#     return run_sql_healing_pipeline(user_query=user_query,session=__context.session,memory=__context.memory,client=__context.client)


# @registry.register(scope="data",input_schema=AnalysisToolInput)
# def run_data_analysis(user_query:str,__context:ToolContext) -> Any:
#     """
#     Run the complete self-healing dataframe analysis pipeline
#     against the dataset associated with the current session.
#     """
#     return run_self_healing_pipeline(user_query=user_query,session=__context.session,memory=__context.memory,client=__context.client)


import hashlib
import pandas as pd
from typing import Optional

from core.logger import get_logger
from models.analysis_tools_schemas import RawCandidate
from tools.profiler import DataProfileResult

logger = get_logger(__name__)

BASELINE_PCT_THRESHOLD = 0.20
ZSCORE_THRESHOLD = 1.5
SEGMENT_PCT_THRESHOLD = 0.30
MIN_SEGMENT_ROWS = 2
MAX_CANDIDATES = 20
MIN_TRAILING_BUCKETS = 2


def detect_anomalies(
    df: pd.DataFrame,
    profile:DataProfileResult,
    baseline_df: Optional[pd.DataFrame] = None,
) -> list[RawCandidate]:
    candidates: list[RawCandidate] = []

    numeric_cols = [
        c.name for c in profile.columns
        if pd.api.types.is_numeric_dtype(df[c.name])
    ]
    time_col = profile.time_column
    cat_cols = [
        c.name for c in profile.columns
        if not pd.api.types.is_numeric_dtype(df[c.name])
        and 1 < c.unique_count <= 50
    ]

    # 1. Global vs baseline
    if baseline_df is not None:
        for col in numeric_cols:
            if col not in baseline_df.columns:
                continue
            curr_mean = df[col].mean()
            base_mean = baseline_df[col].mean()
            if pd.isna(curr_mean) or pd.isna(base_mean) or base_mean == 0:
                continue
            pct = (curr_mean - base_mean) / abs(base_mean)
            if abs(pct) > BASELINE_PCT_THRESHOLD:
                candidates.append(_make_candidate(
                    metric=col, dimension=None, dimension_value=None,
                    magnitude=pct,
                    context={"curr_mean": float(curr_mean),
                             "base_mean": float(base_mean),
                             "pct_change": float(pct),
                              },
                    check="baseline_comparison",
                ))

    # 2. Time-series z-score
    if time_col and time_col in df.columns:
        print(f"ENTERED THE TIME ANALYSIS --------------> XXX")
        ts = df.copy()
        ts[time_col] = pd.to_datetime(ts[time_col], errors="coerce")
        ts = ts.dropna(subset=[time_col]).sort_values(time_col)
    
        for col in numeric_cols:
            series = ts.set_index(time_col)[col].dropna()
            if len(series) < 4:
                continue

            # 1. Safely infer frequency using unique dates only (avoids duplicate index crashes)
            freq = pd.infer_freq(ts[time_col].drop_duplicates().sort_values().head(20))
            try:
                # 2. Auto-map the detected frequency to your bucket rule
                if freq:
                    resample_rule = {"D": "W", "W": "W", "M": "M", "ME": "M"}.get(freq[0], "W")
                buckets = series.resample(resample_rule).mean().dropna()
                print("ENTERED BUCKETS")
                print(buckets)
            except Exception:
                continue
            if len(buckets) < MIN_TRAILING_BUCKETS + 1:
                print("FAILED BUCKETS")
                continue
            latest = buckets.iloc[-1]
            trailing = buckets.iloc[:-1].tail(12)
            if len(trailing) < MIN_TRAILING_BUCKETS:
                continue
            mu = trailing.mean()
            sigma = trailing.std()
            if sigma == 0 or pd.isna(sigma):
                continue
            z = (latest - mu) / sigma
            print("Z - Score :",z)
            if abs(z) > ZSCORE_THRESHOLD:
                candidates.append(_make_candidate(
                    metric=col, dimension=None, dimension_value=None,
                    magnitude=float(z),
                    context={"latest": float(latest), "mu": float(mu),
                             "sigma": float(sigma), "z": float(z),
                             "trailing_buckets": int(len(trailing))},
                    check="timeseries_zscore",
                ))

    # 3. Segment Evolution
    for col in numeric_cols:
        for cat in cat_cols:
            if baseline_df is not None and cat in baseline_df.columns:
                
                base_grouped = baseline_df.groupby(cat)[col].agg(["mean", "count"])
                grouped = df.groupby(cat)[col].agg(["mean", "count"])
                for seg_value, row in grouped.iterrows():
                    if row["count"] < MIN_SEGMENT_ROWS:
                        continue
                    if seg_value not in base_grouped.index:
                        continue
                    base_seg_mean=base_grouped.loc[seg_value,'mean']
                    if pd.isna(base_seg_mean) or base_seg_mean == 0:
                        continue
                
                    pct = (row['mean'] - base_seg_mean) / abs(base_seg_mean)
                    if abs(pct) > SEGMENT_PCT_THRESHOLD:
                        dim_label = f"{cat}({seg_value if seg_value else 'unknown'})"
                        candidates.append(_make_candidate(
                            metric=col, dimension=dim_label,
                            dimension_value=str(seg_value),
                            magnitude=pct,
                            context={"base_seg_mean": float(base_seg_mean),
                                    "present_mean": float(row['mean']),
                                    "pct_change": float(pct),
                                    "segment_rows": int(row["count"])},
                            check="segment_evolution",
                        ))

    # 4. Cap and sort
    result=[]
    candidates.sort(key=lambda c: abs(c.magnitude), reverse=True)
    result = candidates[:MAX_CANDIDATES]
    logger.info(
        "Anomaly detection complete",
        extra={"extra_data": {"candidates": len(result),
                              "total_raw": len(candidates)}},
    )
    return result


def _make_candidate(
    metric: str,
    dimension: Optional[str],
    dimension_value: Optional[str],
    magnitude: float,
    context: dict,
    check: str,
) -> RawCandidate:
    if magnitude > 0:
        direction = "up"
    elif magnitude < 0:
        direction = "down"
    else:
        direction = "flat"

    context_with_direction={
        "direction":direction,
        "magnitude":magnitude,
        **context,
    }

    return RawCandidate(
        category="anomaly",
        metric=metric,
        dimension=dimension,
        dimension_value=dimension_value,
        direction=direction,
        magnitude=round(float(magnitude),2),
        birth_evidence={
            "content": {"check": check},
            "result": context_with_direction,
        },
        raw_context=context_with_direction,
    )


def fingerprint_candidate(c: RawCandidate) -> str:
    key = f"{c.category}|{c.metric}|{c.dimension or ''}|{c.dimension_value or ''}"
    return hashlib.sha256(key.encode()).hexdigest()




