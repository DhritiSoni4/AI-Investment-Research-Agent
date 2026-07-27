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


class SourceCitation(BaseModel):
    title: str
    url: str
    publisher: str
    published_at: datetime | None = None


class AgentArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_name: str
    status: str
    summary: str
    output: dict[str, Any]
    sources: list[SourceCitation]
    created_at: datetime


class ResearchSessionDetail(ResearchSessionRead):
    events: list[ResearchEventRead]
    artifacts: list[AgentArtifactRead] = []
