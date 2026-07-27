import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db_session
from app.schemas.research import (
    CreateResearchSessionRequest,
    ResearchSessionDetail,
    ResearchSessionRead,
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
    return create_research_session(db, request)


@router.get("", response_model=list[ResearchSessionRead])
def list_sessions(db: Session = Depends(get_db_session)) -> list[ResearchSessionRead]:
    return list_research_sessions(db)


@router.get("/{session_id}", response_model=ResearchSessionDetail)
def get_session(session_id: UUID, db: Session = Depends(get_db_session)) -> ResearchSessionDetail:
    try:
        return get_research_session(db, session_id)
    except ResearchSessionNotFoundError as error:
        raise _not_found() from error


@router.get("/{session_id}/events")
async def stream_session_events(
    session_id: UUID, db: Session = Depends(get_db_session)
) -> StreamingResponse:
    try:
        session = get_research_session(db, session_id)
    except ResearchSessionNotFoundError as error:
        raise _not_found() from error

    event_payloads = [
        {"event": event.type, "data": event.model_dump(mode="json")}
        for event in ResearchSessionDetail.model_validate(session).events
    ]

    async def event_stream() -> AsyncIterator[str]:
        for payload in event_payloads:
            yield f"event: {payload['event']}\ndata: {json.dumps(payload['data'], default=str)}\n\n"
            await asyncio.sleep(0.05)
        yield "event: stream.complete\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
