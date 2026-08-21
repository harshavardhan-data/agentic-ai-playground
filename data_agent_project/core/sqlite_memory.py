import os
import pandas as pd
from core.memory import BaseSessionStore,MemoryTurn,SessionState
from typing import Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models.db_models import Base, DBSessionModel, DBTurnModel


class SqliteSessionStore(BaseSessionStore):
    def __init__(self, db_url: str = "sqlite:///./agent_memory.db", max_turns: int = 5, storage_dir: str = "./storage"):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.max_turns = max_turns
        self.csv_dir = os.path.join(storage_dir, "csvs")
        os.makedirs(self.csv_dir, exist_ok=True)

    def _get_db(self) -> Session:
        return self.SessionLocal()

    def get_session(self, session_id: str) -> SessionState:
        with self._get_db() as db:
            db_session = db.query(DBSessionModel).filter(DBSessionModel.session_id == session_id).first()
            
            if not db_session:
                db_session = DBSessionModel(session_id=session_id, sandbox_state={})
                db.add(db_session)
                db.commit()
                db.refresh(db_session)

            # Reconstruct Pydantic turns history
            history = [
                MemoryTurn(
                    user_query=t.user_query,
                    successful_code=t.successful_code,
                    execution_output=t.execution_output,
                    summary=t.summary
                )
                for t in db_session.turns[-self.max_turns:]
            ]

            sandbox_state = dict(db_session.sandbox_state or {})

            # Hydrate DataFrame from disk if csv_path is present
            if "csv_path" in sandbox_state and os.path.exists(sandbox_state["csv_path"]):
                sandbox_state["df"] = pd.read_csv(sandbox_state["csv_path"])

            return SessionState(session_id=session_id, history=history, sandbox_state=sandbox_state)

    def update_sandbox_state(self, session_id: str, key: str, value: Any) -> None:
        """ Persist durable sandbox resources.
        We intentionally do NOT persist live Python objects.
        Instead we persist references to them."""
        with self._get_db() as db:
            db_session = db.query(DBSessionModel).filter(DBSessionModel.session_id == session_id).first()
            if not db_session:
                db_session = DBSessionModel(session_id=session_id, sandbox_state={})
                db.add(db_session)

            current_state = dict(db_session.sandbox_state or {})

            if key == "df" and isinstance(value, pd.DataFrame):
                file_path = os.path.join(self.csv_dir, f"{session_id}.csv")
                value.to_csv(file_path, index=False)
                current_state["csv_path"] = file_path
            else:
                current_state[key] = value

            db_session.sandbox_state = current_state
            db.commit()

    def add_turn(self, session: SessionState, turn: MemoryTurn) -> None:

        """
        Atomic update:
        1. Appends turn to the live in-memory SessionState object.
        2. Persists turn to SQLite.
        3. Enforces max_turns pruning in both RAM and SQLite.
        """
        # --- 1. Immediate In-Memory RAM Sync ---
        session.history.append(turn)
        if len(session.history) > self.max_turns:
            session.history.pop(0)  # Evict oldest turn from RAM

            
        with self._get_db() as db:
            db_turn = DBTurnModel(
                session_id=session.session_id,
                user_query=turn.user_query,
                successful_code=turn.successful_code,
                execution_output=turn.execution_output,
                summary=turn.summary
            )
            db.add(db_turn)
            db.commit()


            # Keep only the newest max_turns in persistent storage.
            turns = (
                db.query(DBTurnModel)
                .filter(DBTurnModel.session_id == session.session_id)
                .order_by(DBTurnModel.id.desc())
                .all()
            )

            for old_turn in turns[self.max_turns :]:
                db.delete(old_turn)

            db.commit()