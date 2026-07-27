from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    query: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_query: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planning", index=True)
    research_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    events: Mapped[list["ResearchEvent"]] = relationship(
        back_populates="research_session", cascade="all, delete-orphan", order_by="ResearchEvent.sequence"
    )
    artifacts: Mapped[list["AgentArtifact"]] = relationship(
        back_populates="research_session", cascade="all, delete-orphan", order_by="AgentArtifact.created_at"
    )


class ResearchEvent(Base):
    __tablename__ = "research_events"
    __table_args__ = (UniqueConstraint("research_session_id", "sequence", name="uq_event_sequence"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    research_session: Mapped[ResearchSession] = relationship(back_populates="events")


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"
    __table_args__ = (UniqueConstraint("research_session_id", "agent_name", name="uq_agent_artifact"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    research_session: Mapped[ResearchSession] = relationship(back_populates="artifacts")
