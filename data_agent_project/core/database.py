from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from contextlib import contextmanager
from collections.abc import Generator
from models.analysis import Base

BASE_DIR=Path(__file__).resolve().parent.parent

DATABASE_URL=f"sqlite:///{BASE_DIR / 'data' / 'prime_db.db'}"


engine=create_engine(url=DATABASE_URL,connect_args={"check_same_thread":False})

SessionLocal=sessionmaker(bind=engine,autocommit=False,autoflush=False)

Base.metadata.create_all(bind=engine)

@contextmanager
def get_db() -> Generator:
    db=SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

