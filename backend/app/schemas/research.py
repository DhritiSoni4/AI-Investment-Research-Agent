from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateResearchSessionRequest(BaseModel):
    query: str = Field(min_length=2, max_length=240, examples=["Analyze NVIDIA"])


class ResearchPlanStep(BaseModel):
    agent: str
    objective: str
    status: str = "queued"


class ResearchPlan(BaseModel):
    objective: str
    steps: list[ResearchPlanStep]


class ResearchEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    type: str
    title: str
    detail: str | None
    payload: dict[str, Any] | None
    created_at: datetime


class ResearchSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query: str
    normalized_query: str
    status: str
    research_plan: ResearchPlan | None
    created_at: datetime
    updated_at: datetime | None


class ResearchSessionDetail(ResearchSessionRead):
    events: list[ResearchEventRead]
