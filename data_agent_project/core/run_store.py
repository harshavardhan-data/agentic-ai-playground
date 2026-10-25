from sqlalchemy.orm import Session
from sqlalchemy import select
import hashlib
import os
from datetime import date
import pandas as pd
import uuid
from core.database import BASE_DIR
from models.analysis import Source,DatasetRun
from core.logger import get_logger

logger=get_logger(__name__)


STORAGE_DIR=BASE_DIR/'storage'/'runs'


def get_source(db:Session,name:str,cadence:str):
    
    stmt=select(Source).where(Source.name == name)
    source=db.scalars(stmt).first()

    if not source:
        source_id=f"src_{uuid.uuid4().hex[:8]}"
        source=Source(
            source_id=source_id,
            name=name,cadence=cadence
        )
        db.add(source)
        db.flush()
    return source


def create_run(db:Session,source_name:str,cadence:str,run_date:date,csv_bytes:bytes) ->DatasetRun:
    # Get or create source
    source=get_source(db,source_name,cadence=cadence)

    # Hash and identifiers
    dataset_hash=hashlib.sha256(csv_bytes).hexdigest()
    run_id=f"run_{uuid.uuid4().hex[:8]}"

    existing = db.scalars(
    select(DatasetRun).where(
        DatasetRun.source_id == source.source_id,
        DatasetRun.dataset_hash == dataset_hash,
    )
    ).first()
    if existing:
        logger.warning(f"Duplicate upload: same hash as run {existing.run_id}")
        # still create a new run, don't skip. Audit trail matters.

    # Ensure storage directory exists and write file
    source_dir=STORAGE_DIR / source.source_id
    source_dir.mkdir(parents=True,exist_ok=True)
    
    storage_ref=source_dir / f"{run_date}_{run_id}.csv"

    with open(storage_ref,"wb") as f:
        f.write(csv_bytes)

    dataset_run=DatasetRun(run_id=run_id,source_id=source.source_id,
                           run_date=run_date,dataset_hash=dataset_hash,storage_ref=str(storage_ref),
                           status="ingested")
    db.add(dataset_run)
    db.flush()

    return dataset_run

def get_run(db:Session,run_id:str) ->DatasetRun:
    stmt=select(DatasetRun).where(DatasetRun.run_id == run_id)
    return db.scalars(stmt).first()

def load_dataframe(run:DatasetRun) -> pd.DataFrame:
    if not run or not os.path.exists(run.storage_ref):
        raise FileNotFoundError(f"Storage reference not found for run: {run.run_id if run else 'Unknown'}")
    return pd.read_csv(run.storage_ref)



