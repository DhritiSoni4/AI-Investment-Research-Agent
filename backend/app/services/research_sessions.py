from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.research import ResearchEvent, ResearchSession
from app.schemas.research import CreateResearchSessionRequest, ResearchPlan

_PLAN_STEPS: Final[tuple[tuple[str, str], ...]] = (
    ("Planner Agent", "Create an auditable research plan and task order."),
    ("Company Profile Agent", "Map the business, segments, competitors, and management."),
    ("Financial Analysis Agent", "Assess financial performance and quality metrics."),
    ("News & SEC Agents", "Collect recent developments and primary-source disclosures."),
    ("Investment Committee", "Synthesize evidence into an investment recommendation."),
)


class ResearchSessionNotFoundError(Exception):
    """Raised when a session ID cannot be located."""


def build_plan(query: str) -> ResearchPlan:
    return ResearchPlan(
        objective=f"Produce an evidence-backed research brief for: {query}",
        steps=[{"agent": agent, "objective": objective} for agent, objective in _PLAN_STEPS],
    )


def create_research_session(db: Session, request: CreateResearchSessionRequest) -> ResearchSession:
    query = request.query.strip()
    plan = build_plan(query)
    session = ResearchSession(
        query=query,
        normalized_query=query.casefold(),
        status="planned",
        research_plan=plan.model_dump(),
    )
    db.add(session)
    db.flush()

    events = [
        ResearchEvent(
            research_session_id=session.id,
            sequence=1,
            type="research.started",
            title="Research session created",
            detail=f"Preparing a research plan for {query}.",
        ),
        ResearchEvent(
            research_session_id=session.id,
            sequence=2,
            type="plan.created",
            title="Research plan ready",
            detail="Five specialized agents have been queued. No model reasoning is exposed.",
            payload=plan.model_dump(),
        ),
    ]
    db.add_all(events)
    db.commit()
    return get_research_session(db, session.id)


def get_research_session(db: Session, session_id: UUID) -> ResearchSession:
    statement = (
        select(ResearchSession)
        .options(selectinload(ResearchSession.events), selectinload(ResearchSession.artifacts))
        .where(ResearchSession.id == session_id)
    )
    session = db.scalar(statement)
    if session is None:
        raise ResearchSessionNotFoundError
    return session


def list_research_sessions(db: Session) -> list[ResearchSession]:
    return list(db.scalars(select(ResearchSession).order_by(ResearchSession.created_at.desc())))
