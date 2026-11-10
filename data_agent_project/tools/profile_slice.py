from models.analysis import DatasetRun, Finding


def build_profile_dict(run: DatasetRun) -> dict:
    """Build once per run. Returns {'base': {...}, 'columns': {name: profile}}."""
    schema_json = run.schema_json or []
    stats_json = run.stats_json or {}

    columns: dict = {}
    for c in schema_json:
        name = c["name"]
        col = {
            "dtype": c.get("dtype"),
            "null_pct": c.get("null_pct"),
        }
        if name in stats_json:
            col["stats"] = stats_json[name]
        if c.get("unique_count") is not None:
            col["unique_count"] = c["unique_count"]
        if c.get("top_values"):
            col["top_values"] = c["top_values"]
        columns[name] = col

    filtered = [
        c for c in schema_json
        if c.get("dtype") in ("str", "object", "category")
        and c.get("unique_count") is not None
        and 2 <= c["unique_count"] <= 20
        and (c.get("null_pct") or 0) < 40
    ]
    candidate_dims = [
        {"name": c["name"], "unique_count": c["unique_count"], "null_pct": c.get("null_pct")}
        for c in sorted(filtered, key=lambda x: x.get("null_pct") or 0)[:3]
    ] or None

    num_cols = run.col_count or len(schema_json)
    total_cells = (run.row_count or 0) * num_cols
    total_nulls = sum((c.get("null_count") or 0) for c in schema_json)

    base = {
        "row_count": run.row_count,
        "time_column": run.time_column,
        "nulls_summary": float(total_nulls / total_cells) if total_cells else 0.0,
        "candidate_dims": candidate_dims,
    }
    return {"base": base, "columns": columns}


def profile_for(finding: Finding, profile_dict: dict) -> dict:
    """Assemble the per-finding slice from the shared dict."""
    base = profile_dict["base"]
    cols = profile_dict["columns"]

    return {
        "row_count": base["row_count"],
        "time_column": base["time_column"],
        "nulls_summary": base["nulls_summary"],
        "candidate_dims": base["candidate_dims"] if not finding.dimension else None,
        "target": cols.get(finding.metric, {}),
        "dimension": cols.get(finding.dimension, {}) if finding.dimension else {},
    }