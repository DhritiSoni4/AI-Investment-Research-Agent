from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    service: str


@router.get("", response_model=HealthResponse, summary="Service health check")
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(UTC), service="alphaagent-api")
