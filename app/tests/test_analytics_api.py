import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api.main import create_app
from app.domain.schemas import EngagementRecord
from app.persistence.models import create_all
from app.persistence.repositories import EngagementRepo
from app.persistence.session import session_scope
from app.tests.test_api import NOW, _StubRenderer, _drive_to_delivered, _drive_to_locked, _new_version, _seed


@pytest.fixture
def api_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", future=True,
        poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    create_all(engine)
    return engine


@pytest.fixture
def client(api_engine):
    app = create_app(engine=api_engine)
    app.dependency_overrides[deps.now] = lambda: NOW
    app.dependency_overrides[deps.render_adapter] = _StubRenderer
    with TestClient(app) as test_client:
        yield test_client


def _add_events(engine, version_id: str) -> None:
    with session_scope(engine) as session:
        records = [
            EngagementRecord(id="eng-sent", proposal_version_id=version_id, provider="pandadoc", type="sent", document_id="doc-1", at="2026-08-01T09:00:00Z"),
            EngagementRecord(id="eng-viewed", proposal_version_id=version_id, provider="pandadoc", type="viewed", document_id="doc-1", at="2026-08-02T12:00:00Z"),
            EngagementRecord(id="eng-signed", proposal_version_id=version_id, provider="pandadoc", type="signed", document_id="doc-1", at="2026-08-03T15:00:00Z"),
        ]
        for record in records:
            EngagementRepo(session).add(record)


def test_engagement_endpoint_returns_kpis_events_and_views(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_delivered(client, version_id)
    _add_events(api_engine, version_id)

    body = client.get("/v1/analytics/engagement").json()
    assert {item["key"] for item in body["kpis"]} == {
        "proposals_sent", "win_rate", "median_cycle_days", "pipeline_value",
    }
    assert body["events"] and body["viewsByDay"]


def test_pipeline_value_is_reported_in_minor_units(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_delivered(client, version_id)
    _add_events(api_engine, version_id)

    kpi = next(item for item in client.get("/v1/analytics/engagement").json()["kpis"]
               if item["key"] == "pipeline_value")
    assert isinstance(kpi["valueMinor"], int)


def test_provider_events_never_mutate_a_locked_version(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_locked(client, version_id)
    before = client.get(f"/v1/proposal-versions/{version_id}").json()

    response = client.post("/v1/engagement/webhook", json={
        "provider": "pandadoc", "type": "viewed",
        "proposalVersionId": version_id, "at": "2026-08-02T12:00:00Z",
    })

    assert response.status_code == 201, response.text
    after = client.get(f"/v1/proposal-versions/{version_id}").json()
    assert before == after
    assert any(item["type"] == "viewed"
               for item in client.get("/v1/analytics/engagement").json()["events"])
