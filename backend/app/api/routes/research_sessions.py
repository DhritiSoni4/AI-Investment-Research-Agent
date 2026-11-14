import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.research import ResearchEvent, ResearchSession
from app.infrastructure.database import get_db_session, get_session_factory
from app.schemas.research import (
    CreateResearchSessionRequest,
    ResearchEventRead,
    ResearchSessionDetail,
    ResearchSessionRead,
)
from app.services.research_execution import (
    ResearchAlreadyExecutedError,
    ResearchExecutionNotFoundError,
    execute_research,
    request_execution,
)
from app.services.research_sessions import (
    ResearchSessionNotFoundError,
    create_research_session,
    get_research_session,
    list_research_sessions,
)

router = APIRouter()


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research session not found")


@router.post("", response_model=ResearchSessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(
    request: CreateResearchSessionRequest, db: Session = Depends(get_db_session)
) -> ResearchSessionDetail:
    return ResearchSessionDetail.model_validate(create_research_session(db, request))


@router.get("", response_model=list[ResearchSessionRead])
def list_sessions(db: Session = Depends(get_db_session)) -> list[ResearchSessionRead]:
    return [ResearchSessionRead.model_validate(item) for item in list_research_sessions(db)]


@router.get("/{session_id}", response_model=ResearchSessionDetail)
def get_session(session_id: UUID, db: Session = Depends(get_db_session)) -> ResearchSessionDetail:
    try:
        return ResearchSessionDetail.model_validate(get_research_session(db, session_id))
    except ResearchSessionNotFoundError as error:
        raise _not_found() from error


@router.post(
    "/{session_id}/execute",
    response_model=ResearchSessionRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def execute_session(
    session_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db_session)
) -> ResearchSessionRead:
    try:
        session = request_execution(db, session_id)
    except ResearchExecutionNotFoundError as error:
        raise _not_found() from error
    except ResearchAlreadyExecutedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only planned research sessions can be executed once.",
        ) from error
    background_tasks.add_task(execute_research, session.id)
    return ResearchSessionRead.model_validate(session)


@router.get("/{session_id}/events")
async def stream_session_events(
    session_id: UUID,
    db: Session = Depends(get_db_session),
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> StreamingResponse:
    try:
        get_research_session(db, session_id)
    except ResearchSessionNotFoundError as error:
        raise _not_found() from error

    async def event_stream() -> AsyncIterator[str]:
        last_sequence = 0
        terminal_statuses = {"planned", "completed", "partial_failure", "failed"}
        while True:
            event_db = session_factory()
            try:
                events = list(
                    event_db.scalars(
                        select(ResearchEvent)
                        .where(
                            ResearchEvent.research_session_id == session_id,
                            ResearchEvent.sequence > last_sequence,
                        )
                        .order_by(ResearchEvent.sequence)
                    )
                )
                current_status = event_db.scalar(
                    select(ResearchSession.status).where(ResearchSession.id == session_id)
                )
            finally:
                event_db.close()
            for event in events:
                serialized = ResearchEventRead.model_validate(event).model_dump(mode="json")
                yield f"event: research.event\ndata: {json.dumps(serialized)}\n\n"
                last_sequence = event.sequence
            if current_status in terminal_statuses and not events:
                break
            await asyncio.sleep(0.25)
        yield "event: stream.complete\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
