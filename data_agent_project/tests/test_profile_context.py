from core.weekly_review import build_critic_context
from core.database import get_db
from models.analysis import Source,Finding
from sqlalchemy import select
from tools.profiler import DataProfileResult

finding=None
mock_run=None

with get_db() as db:
    source = db.scalars(select(Source).where(Source.name=="Mynras")).first()

    finding=source.findings[0]
    
    mock_run=finding.run

    # Temporarily mutate for testing
    finding.dimension = "region"  # Change this to match an actual column name in your schema
    
   
    mock_profile_result=DataProfileResult(row_count=125,col_count=10,quality_flags=[{}],time_column=None,columns=[])

    print(build_critic_context(finding=finding,profile_result=mock_profile_result,run=mock_run))