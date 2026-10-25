from pydantic import BaseModel
from typing import Any,List,Optional,Dict
import pandas as pd


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float
    unique_count: int
    # optional — only populated for numeric
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    p25:float | None = None
    p75:float | None = None
    # optional — only populated for low-cardinality categoricals
    top_values: list[tuple[str, int]] | None = None

class DataProfileResult(BaseModel):
    row_count: int
    col_count: int
    columns: list[ColumnProfile]
    time_column: str | None
    quality_flags: list[dict]



def inspect_dataframe(df:pd.DataFrame) -> DataProfileResult:

    row_count=len(df)
    col_count=len(df.columns)
    columns=[]

    for col in df.columns:
        series=df[col]
        dtype_str=str(series.dtype)
        unique_count=int(series.nunique(dropna=True))
        profile=ColumnProfile(
            name=col,
            dtype=dtype_str,
            null_count=int(series.isna().sum()),
            null_pct=round(float(series.isna().mean()*100),2),
            unique_count=unique_count,
        )

        # numeric extras
        if pd.api.types.is_numeric_dtype(series):
            profile.min=_safe_float(series.min())
            profile.max=_safe_float(series.max())
            profile.mean=_safe_float(series.mean())
            profile.median=_safe_float(series.median())
            profile.p25=_safe_float(series.quantile(0.25))
            profile.p75=_safe_float(series.quantile(0.75))


        # categorical extras -only if low cardinality
        elif unique_count <= 50  and unique_count > 1:
            top = series.value_counts().head(5)
            profile.top_values=[(str(k),int(v)) for k,v in top.items()]

        columns.append(profile)

    # 2. Time Column Detection
    time_column = _detect_time_column(df,columns)
    # 3 . Quality Flags
    quality_flags=_compute_quality_flags(df,columns,time_column)

    return DataProfileResult(row_count=row_count,col_count=col_count,
                             columns=columns,time_column=time_column,
                             quality_flags=quality_flags)


def _safe_float(v):
    return None if pd.isna(v) else float(v)


def _detect_time_column(df:pd.DataFrame,columns:list[ColumnProfile]) -> str | None :
    time_candidates={}
    for col_profile in columns:
        col_name=col_profile.name
        series=df[col_name]
        dtype=col_profile.dtype
        if pd.api.types.is_datetime64_any_dtype(series):
            time_candidates[col_name]=col_profile.unique_count
        elif "object" in dtype or "string" in dtype or pd.api.types.is_string_dtype(series):
            sample=series.head(1000)
            parsed=pd.to_datetime(sample,errors='coerce',format="%Y-%m-%d")
            if len(series)>0 and parsed.notna().mean()>0.9:
                time_candidates[col_name]=col_profile.unique_count

    return max(time_candidates,key=time_candidates.get) if time_candidates else None

def _compute_quality_flags(df: pd.DataFrame, columns: list[ColumnProfile], time_column: Optional[str]) -> List[Dict[str, Any]]:
    quality_flags = []
    row_count = len(df)
    positive_metric_keywords = ("price", "revenue", "amount", "count")
    numeric_cols=[]
    # Global check: duplicate rows
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        quality_flags.append({
            "type": "duplicate_rows",
            "column": None,
            "severity": "warn",
            "detail": f"Found {dup_count} duplicate rows in the dataframe"
        })
    
    for col_profile in columns:
        col_name = col_profile.name
        series = df[col_name]

        # High nulls check (Fixed severity split: >50 is warn, >20 is info)
        if col_profile.null_pct > 50:
            quality_flags.append({
                "type": "high_nulls",
                "column": col_name,
                "severity": "warn",
                "detail": f"Null percentage is {col_profile.null_pct}% (>50%)."
            })
        elif col_profile.null_pct > 20:
            quality_flags.append({
                "type": "high_nulls",
                "column": col_name,
                "severity": "info",
                "detail": f"Null percentage is {col_profile.null_pct}% (>20%)."
            })

        # Constant column check
        if col_profile.unique_count == 1:
            quality_flags.append({
                "type": "constant_column",
                "column": col_name,
                "severity": "info",
                "detail": "Column contains only a single unique value."
            })

        is_numeric = pd.api.types.is_numeric_dtype(series)

        # High cardinality categorical check
        if not is_numeric and col_profile.unique_count > (0.8 * row_count):
            quality_flags.append({
                "type": "high_cardinality",
                "column": col_name,
                "severity": "info",
                "detail": f"High cardinality: {col_profile.unique_count} unique values out of {row_count} rows."
            })

        # Negative values in positive metrics heuristic
        if is_numeric and any(kw in col_name.lower() for kw in positive_metric_keywords):
            if (series < 0).any():
                quality_flags.append({
                    "type": "negative_in_positive_metric",
                    "column": col_name,
                    "severity": "warn",
                    "detail": "Column name implies a positive metric, but contains negative values."
                })

        if is_numeric:
            numeric_cols.append(col_name)

    # 3. Time gaps check (Fixed indentation: OUTSIDE the column loop)
    if time_column and time_column in df.columns:
        time_series = pd.to_datetime(df[time_column], errors="coerce").dropna().sort_values()
        if len(time_series) > 2:
            inferred_freq = pd.infer_freq(time_series.head(100))
            if inferred_freq:
                full_range = pd.date_range(start=time_series.min(), end=time_series.max(), freq=inferred_freq)
                missing_count = len(full_range.difference(time_series))
                if missing_count > 0:
                    quality_flags.append({
                        "type": "time_gaps",
                        "column": time_column,
                        "severity": "info",
                        "detail": f"Detected {missing_count} missing periods based on inferred frequency ({inferred_freq})."
                    })

    # 4 Correlation check between numeric cols
    correlation=df[numeric_cols].corr()

    



    return quality_flags