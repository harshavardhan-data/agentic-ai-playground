from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    cadence: Mapped[str] = mapped_column(String, nullable=False)  # weekly/monthly/adhoc
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    runs: Mapped[List["DatasetRun"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    findings: Mapped[List["Finding"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    memories: Mapped[List["AgentMemory"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class DatasetRun(Base):
    __tablename__ = "dataset_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String, ForeignKey("sources.source_id"), nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String, nullable=False)
    storage_ref: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # ingested/profiled/analyzed/failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    schema_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    stats_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    time_column: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    quality_flags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    source: Mapped["Source"] = relationship(back_populates="runs")
    findings: Mapped[List["Finding"]] = relationship(back_populates="run",foreign_keys="Finding.run_id", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    finding_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("dataset_runs.run_id"), nullable=False)
    source_id: Mapped[str] = mapped_column(String, ForeignKey("sources.source_id"), nullable=False)
    
    fingerprint: Mapped[str] = mapped_column(String, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)  # anomaly/trend/driver/quality
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dimension: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # direction: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # up/down/flat
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # new/ongoing/resolved/contradicted
    
    first_seen_run_id: Mapped[str] = mapped_column(String, ForeignKey("dataset_runs.run_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    run: Mapped["DatasetRun"] = relationship(back_populates="findings", foreign_keys=[run_id])
    source: Mapped["Source"] = relationship(back_populates="findings")
    evidence: Mapped[List["Evidence"]] = relationship(back_populates="finding", cascade="all, delete-orphan")
    triggered_memories: Mapped[List["AgentMemory"]] = relationship(back_populates="trigger_finding")


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String, primary_key=True)
    finding_id: Mapped[str] = mapped_column(String, ForeignKey("findings.finding_id"), nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)  # tool/investigation/user
    type: Mapped[str] = mapped_column(String, nullable=False)  # sql/python/stat/comparison/counter
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    supports: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    finding: Mapped["Finding"] = relationship(back_populates="evidence")


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    memory_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String, ForeignKey("sources.source_id"), nullable=False)
    error_type: Mapped[str] = mapped_column(String, nullable=False)  # hallucination/false_alarm/bad_assumption/missed
    lesson: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Only nullable because a manual lesson might not trace back to an automated finding
    trigger_finding_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("findings.finding_id"), nullable=True)
    
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    source: Mapped["Source"] = relationship(back_populates="memories")
    trigger_finding: Mapped[Optional["Finding"]] = relationship(back_populates="triggered_memories")


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    sandbox_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)