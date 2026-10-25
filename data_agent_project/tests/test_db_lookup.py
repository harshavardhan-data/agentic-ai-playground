from core.database import get_db
from sqlalchemy import select
from models.analysis import Finding,Evidence,DatasetRun,Source


with get_db() as db:
    sources = db.scalars(select(Source).where(Source.name=="Konstin")).all()
    for s in sources:
        print(f"\nSource: {s.name} (ID: {s.source_id}, Cadence: {s.cadence})")
        print(f"Total Runs: {len(s.runs)}")
        
        for r in s.runs:
            print(f"  -> Run ID: {r.run_id} | Date: {r.run_date} | Status: {r.status}")
            print(f"TIME COLUMN : ",r.time_column)
            # print(f"SCHEMA JSON ",r.schema_json)

        for f in s.findings:
            print(f"  -> Finding ID: {f.finding_id} | Category: {f.category} | Status: {f.status}")
            print(f"  -> Metric : {f.metric} | Dimension : {f.dimension}")
            for e in f.evidence:
                print(f"[Evidence Details] E_id: {e.evidence_id} | Origin: {e.origin} | Created at: {e.created_at}")
                print(f"[Evidence Details] Content_json: {e.content_json} | Result json : {e.result_json}")

