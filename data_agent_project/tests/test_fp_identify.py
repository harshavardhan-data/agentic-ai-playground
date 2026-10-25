from core.run_store import create_run
from core.weekly_review import run_weekly_review
import pandas as pd
from models.analysis import DatasetRun,Finding,Evidence
from datetime import date,timedelta,datetime
import numpy as np
from sqlalchemy import select
from core.database import get_db


# with open("testing_csvs/run1_january_clean.csv", "rb") as f:
#         run1_df_bytes=f.read()

# with open("testing_csvs/run2_february_anomaly_and_quality.csv", "rb") as f:
#         run2_df_bytes=f.read()

with open("testing_csvs/run3_march_clean_recovery.csv", "rb") as f:
        run3_df_bytes=f.read()

# print(run1_df_bytes)

with get_db() as db:
    
    # run1=create_run(db,source_name="Konstin",cadence="weekly",run_date=date(2026,4,1),csv_bytes=run1_df_bytes)
    # print(f"SUCCESSFULLY CREATED RUN :{run1.run_id} ,{run1.source.name}")
    # run1_summary=run_weekly_review(db,run1.run_id)
    # print(run1_summary)

   
    # run2=create_run(db,source_name="Konstin",cadence="weekly",run_date=date(2026,5,1),csv_bytes=run2_df_bytes)
    # print(f"SUCCESSFULLY CREATED RUN :{run2.run_id} ,{run2.source.name}")
    # run2_summary=run_weekly_review(db,run2.run_id)
    # print(run2_summary)


    run3=create_run(db,source_name="Konstin",cadence="weekly",run_date=date(2026,6,1),csv_bytes=run3_df_bytes)
    print(f"SUCCESSFULLY CREATED RUN :{run3.run_id} ,{run3.source.name}")
    run3_summary=run_weekly_review(db,run3.run_id)
    print(run3_summary)




