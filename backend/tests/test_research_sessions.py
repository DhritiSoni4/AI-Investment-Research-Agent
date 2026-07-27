from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database import Base, get_db_session
from app.main import app


@pytest.fixture
def client(tmp_path: pytest.TempPathFactory) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_creates_session_and_exposes_a_plan(client: TestClient) -> None:
    response = client.post("/api/v1/research-sessions", json={"query": "Analyze NVIDIA"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "planned"
    assert body["normalized_query"] == "analyze nvidia"
    assert len(body["research_plan"]["steps"]) == 5
    assert [event["type"] for event in body["events"]] == ["research.started", "plan.created"]


def test_streams_persisted_execution_events(client: TestClient) -> None:
    created = client.post("/api/v1/research-sessions", json={"query": "Analyze NVDA"}).json()

    response = client.get(f"/api/v1/research-sessions/{created['id']}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: research.started" in response.text
    assert "event: plan.created" in response.text
    assert "event: stream.complete" in response.text


def test_returns_404_for_unknown_session(client: TestClient) -> None:
    response = client.get("/api/v1/research-sessions/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
