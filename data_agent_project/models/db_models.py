from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import String, Integer, Text, JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DBSessionModel(Base):     
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Stores JSON metadata like {"csv_path": "storage/csvs/123.csv", "db_path": "data/app.db"}
    sandbox_state: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)

    # 1-to-Many relationship with turn history
    turns: Mapped[List[DBTurnModel]] = relationship(
        "DBTurnModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DBTurnModel.id",
    )


class DBTurnModel(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), index=True
    )
    
    user_query: Mapped[str] = mapped_column(Text)
    successful_code: Mapped[str] = mapped_column(Text)
    execution_output: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)

    session: Mapped[DBSessionModel] = relationship("DBSessionModel", back_populates="turns")