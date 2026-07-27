from datetime import datetime

from pydantic import BaseModel


class ToolSource(BaseModel):
    title: str
    url: str
    publisher: str
    published_at: datetime | None = None


class ResolvedCompany(BaseModel):
    ticker: str
    name: str
    exchange: str | None = None


class ToolFailure(Exception):
    """An expected external-provider failure that agents can report safely."""
