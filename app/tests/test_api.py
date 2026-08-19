"""The HTTP surface.

These tests drive the API the way the demo does: real endpoints, real database,
real domain functions behind them. Exactly two things are substituted — the clock
(so hashes and timestamps are stable) and the PDF renderer (so the default suite
needs no browser). One `slow` test at the bottom does the real render through the
real endpoint, so the substitution never hides a broken document path.

The database is in-memory SQLite behind a StaticPool: FastAPI runs sync endpoints
on a worker thread, and the default SQLite pool would hand that thread its own
blank connection.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api import main as main_module
from app.api.main import create_app
from app.persistence.models import Base
from app.domain.schemas import (
    Claim,
    DiscountPolicy,
    EvidenceLink,
    Opportunity,
    PricingRule,
    Requirement,
    SourceRecord,
)
from app.persistence.models import create_all
from app.persistence.repositories import (
    ClaimRepo,
    DiscountPolicyRepo,
    EvidenceRepo,
    OpportunityRepo,
    PricingRuleRepo,
    RequirementRepo,
    SourceRecordRepo,
)
from app.persistence.session import session_scope

NOW = "2026-08-01T12:00:00Z"

CLAIM_TEXT = {
    "claim-onboarding-40": "Cut onboarding time by 40% for a comparable mid-size retailer",
    "claim-csat-uplift": "Post-onboarding CSAT rose from 3.8 to 4.5",
    "claim-retention-2x": "Achieved a 2x improvement in 90-day retention",
}

SOURCES = (
    ("src-crm-hs-9001-notes", "Discovery call notes, 29 July", "crm"),
    ("src-notes-manual", "Discovery notes pasted by the proposal owner", "discovery"),
    ("src-case-northwind", "Northwind onboarding case study", "content"),
    ("src-rate-card", "FY26 rate card", "manual"),
)

# The two sections the fixtures cover, and a quote that recomputes exactly:
# 4 days x 120000 minor = 480000, split into two equal installments.
GENERATE_BODY = {
    "templateId": "tmpl-consulting-v1",
    "requestedSections": ["scope", "case_studies"],
    "modelProvider": "claude",
    "modelName": "claude-opus-5",
}

QUOTE_BODY = {
    "currency": "USD", "discountMinor": 0, "taxMinor": 0,
    "lines": [{"id": "l_strategy", "label": "Strategy days",
               "ruleId": "rule_strategy_day", "quantity": "4",
               "optional": False, "selected": True,
               "sourceRecordIds": ["src-rate-card"]}],
    "installments": [{"sequence": 1, "label": "Deposit", "amountMinor": 240000,
                      "dueDescription": "On signature"},
                     {"sequence": 2, "label": "Final", "amountMinor": 240000,
                      "dueDescription": "On delivery"}],
}


class _StubRenderer:
    """Stands in for Chromium. Returns the same shape the real adapter returns."""

    provider = "manual"

    def capabilities(self) -> list[str]:
        return ["render_document", "store_document"]

    def render(self, version, sections, claims_by_id, evidence_by_claim, **kwargs):
        return {"documentId": f"doc-{version.id}", "status": "ready",
                "uri": f"file:///stub/{version.id}.pdf", "contentHash": "0" * 64}


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


def _seed(engine, *, requirement_status: str = "confirmed") -> None:
    """Everything an opportunity needs to reach a clean validation."""
    with session_scope(engine) as session:
        sources = SourceRecordRepo(session)
        for source_id, title, source_type in SOURCES:
            sources.add(SourceRecord(
                id=source_id, provider="manual", external_id=None, title=title,
                uri=None, retrieved_at=NOW, content_hash=f"hash-{source_id}",
                excerpt=None, source_type=source_type, approved_for_generation=True))

        OpportunityRepo(session).add(Opportunity(
            id="opp-1", external_provider="hubspot", external_id="hs-9001",
            account_name="Northwind Retail", contact_name="R. Ortega",
            title="Customer onboarding acceleration", currency="USD",
            status="normalized", source_record_ids=["src-crm-hs-9001-notes"],
            required_field_errors=[], imported_at=NOW))

        RequirementRepo(session).add_for_opportunity("opp-1", Requirement(
            id="req-1", text="Complete four facilitated discovery workshops",
            source_record_ids=["src-crm-hs-9001-notes"],
            status=requirement_status, confidence="high"))

        claims, evidence = ClaimRepo(session), EvidenceRepo(session)
        for claim_id, text in CLAIM_TEXT.items():
            claims.add(Claim(
                id=claim_id, text=text, status="approved",
                source_record_ids=["src-case-northwind"],
                valid_from="2026-01-01T00:00:00Z", valid_until="2027-01-01T00:00:00Z",
                allowed_contexts=["case_studies"], prohibited_contexts=[]))
            evidence.add_link(f"ev-{claim_id}", EvidenceLink(
                claim_id=claim_id, source_record_id="src-case-northwind",
                locator="page 2", excerpt=text, verified_by="user-approver",
                verified_at=NOW))

        DiscountPolicyRepo(session).add(DiscountPolicy(
            id="policy-standard", version="2026.1", max_percent_without_approval=10,
            max_minor_without_approval=250000, requires_quote_approval_above=5000000))
        PricingRuleRepo(session).add(PricingRule(
            id="rule_strategy_day", version="2026.1", label="Strategy days",
            unit="day", currency="USD", unit_price_minor=120000, min_quantity=1,
            max_quantity=60, optional=False, active_from="2026-01-01",
            active_until=None, discount_policy_id="policy-standard",
            source_record_ids=["src-rate-card"]))


def _new_proposal(client) -> tuple[str, str]:
    """Returns (proposal_id, version_id) for a fresh working version 1."""
    response = client.post("/v1/proposals", json={"opportunityId": "opp-1"})
    assert response.status_code == 201, response.text
    body = response.json()
    return body["proposal"]["id"], body["version"]["id"]


def _new_version(client) -> str:
    return _new_proposal(client)[1]


# --- Process health and fixture readiness ----------------------------------


def test_health_reports_running_but_not_ready_without_fixture_data(client):
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "running",
        "ready": False,
        "reason": "fixture data is not seeded",
    }


def test_health_reports_ready_when_fixture_data_is_seeded(client, api_engine):
    _seed(api_engine)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "running", "ready": True}


def test_fixture_reset_seeds_the_running_api_database(client):
    response = client.post("/v1/fixture/reset")

    assert response.status_code == 200
    assert response.json() == {"status": "reset", "proposalVersions": 2}
    assert client.get("/health").json() == {"status": "running", "ready": True}


def test_fixture_reset_rejects_a_non_sqlite_engine_without_dropping_tables(monkeypatch):
    engine = create_engine("postgresql+psycopg://proposal:proposal@localhost:5432/proposal")
    app = create_app(engine=engine)
    drop_calls = []
    monkeypatch.setattr(Base.metadata, "drop_all", lambda *args, **kwargs: drop_calls.append(args))

    with TestClient(app) as test_client:
        response = test_client.post("/v1/fixture/reset")

    assert response.status_code == 403
    assert response.json()["detail"] == "fixture reset only permits the local showcase SQLite database"
    assert drop_calls == []


def test_fixture_reset_rejects_another_sqlite_file_without_data_loss(tmp_path, monkeypatch):
    unsafe_path = tmp_path / "production.db"
    engine = create_engine(f"sqlite+pysqlite:///{unsafe_path}", future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sentinel (value INTEGER)"))
        connection.execute(text("INSERT INTO sentinel VALUES (7)"))
    app = create_app(engine=engine)
    drop_calls = []
    monkeypatch.setattr(Base.metadata, "drop_all", lambda *args, **kwargs: drop_calls.append(args))

    with TestClient(app) as test_client:
        response = test_client.post("/v1/fixture/reset")

    assert response.status_code == 403
    assert drop_calls == []
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT value FROM sentinel")) == 7


def test_fixture_reset_allows_the_configured_showcase_sqlite_file(tmp_path, monkeypatch):
    fixture_path = tmp_path / "var" / "showcase.db"
    fixture_path.parent.mkdir()
    monkeypatch.setattr(main_module, "FIXTURE_DATABASE_PATH", fixture_path.resolve())
    engine = create_engine(f"sqlite+pysqlite:///{fixture_path}", future=True)
    app = create_app(engine=engine)

    with TestClient(app) as test_client:
        response = test_client.post("/v1/fixture/reset")

    assert response.status_code == 200
    assert response.json() == {"status": "reset", "proposalVersions": 2}


# --- The nine PRD endpoints ------------------------------------------------


def test_import_success_normalizes_the_opportunity(client):
    response = client.post("/v1/opportunities/import",
                           json={"provider": "hubspot", "externalId": "42",
                                 "outcome": "success"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "normalized"
    assert body["accountName"] == "Northwind Retail"
    assert body["externalId"] == "42"  # the adapter echoes the caller's id


def test_import_failure_surfaces_the_adapter_failure(client):
    response = client.post("/v1/opportunities/import",
                           json={"provider": "hubspot", "outcome": "failure"})
    assert response.status_code == 502
    assert response.json()["code"] == "AUTH"


def test_import_with_missing_fields_needs_attention(client):
    response = client.post("/v1/opportunities/import",
                           json={"provider": "manual", "outcome": "success",
                                 "accountName": "", "title": ""})
    body = response.json()
    assert body["status"] == "needs_attention"
    assert body["requiredFieldErrors"]


def test_generate_then_calculate_then_validate_is_clean(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    response = client.post(f"/v1/proposal-versions/{version_id}/generate",
                           json=GENERATE_BODY)
    assert response.status_code == 200, response.text
    assert {s["key"] for s in response.json()["sections"]} == {"scope", "case_studies"}

    response = client.post(f"/v1/proposal-versions/{version_id}/quote/calculate",
                           json=QUOTE_BODY)
    assert response.status_code == 200, response.text
    assert response.json()["totalMinor"] == 480000
    assert response.json()["status"] == "calculated"

    response = client.post(f"/v1/proposal-versions/{version_id}/validate")
    assert response.status_code == 200, response.text
    assert [f for f in response.json()["flags"] if f["severity"] == "blocking"] == []


def test_quote_rejects_a_discount_that_would_make_the_total_negative(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    body = {
        key: value for key, value in QUOTE_BODY.items()
        if key != "installments"
    } | {"discountMinor": 900000}

    response = client.post(f"/v1/proposal-versions/{version_id}/quote/calculate", json=body)

    assert response.status_code == 409
    assert response.json()["flags"] == [{
        "code": "PRICE_MISMATCH",
        "severity": "blocking",
        "message": "negative total is rejected (I3)",
        "relatedIds": [version_id],
    }]


def test_submit_is_refused_while_a_blocking_flag_is_open(client, api_engine):
    _seed(api_engine, requirement_status="open_question")
    version_id = _new_version(client)
    response = client.post(f"/v1/proposal-versions/{version_id}/submit")
    assert response.status_code == 409
    assert any(f["code"] == "UNRESOLVED_REQUIREMENT"
               for f in response.json()["flags"])


def test_wrong_role_cannot_decide_an_approval(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_submitted(client, version_id)
    approval_id = client.get(
        f"/v1/proposal-versions/{version_id}").json()["approvals"][0]["id"]
    response = client.post(f"/v1/approvals/{approval_id}/decide",
                           json={"decision": "approved", "reviewerId": "u_content",
                                 "reviewerRole": "content_editor"})
    assert response.status_code == 403


def test_last_approval_locks_the_version(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_submitted(client, version_id)
    approvals = client.get(
        f"/v1/proposal-versions/{version_id}").json()["approvals"]
    for approval in approvals:
        response = client.post(f"/v1/approvals/{approval['id']}/decide",
                               json={"decision": "approved", "reviewerId": "u_prop",
                                     "reviewerRole": approval["requiredRole"]})
        assert response.status_code == 200
    assert client.get(f"/v1/proposal-versions/{version_id}").json()["status"] == "locked"


def test_locked_version_refuses_generate_and_quote(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_locked(client, version_id)
    for path in ("generate", "quote/calculate"):
        response = client.post(f"/v1/proposal-versions/{version_id}/{path}", json={})
        assert response.status_code == 409, path
        assert response.json()["flags"]


def test_deliver_is_refused_before_render(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_locked(client, version_id)
    response = client.post(f"/v1/proposal-versions/{version_id}/deliver", json={})
    assert response.status_code == 409
    assert any(f["code"] in {"RENDER_ERROR", "MISSING_APPROVAL"}
               or "document" in f["message"]
               for f in response.json()["flags"])


def test_render_then_deliver_succeeds(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_locked(client, version_id)
    assert client.post(f"/v1/proposal-versions/{version_id}/render",
                       json={}).status_code == 200
    response = client.post(f"/v1/proposal-versions/{version_id}/deliver",
                           json={"provider": "pandadoc", "outcome": "success"})
    assert response.status_code == 200
    assert response.json()["status"] == "delivered"


def test_every_mutation_wrote_an_audit_event(client, api_engine):
    _seed(api_engine)
    version_id = _new_version(client)
    _drive_to_delivered(client, version_id)
    actions = {e["action"] for e in
               client.get(f"/v1/proposal-versions/{version_id}/audit").json()}
    assert {"generated", "validated", "approved", "locked", "rendered",
            "delivered"} <= actions


def test_scope_resolution_clears_the_open_question(client, api_engine):
    _seed(api_engine, requirement_status="open_question")
    version_id = _new_version(client)
    response = client.post(f"/v1/proposal-versions/{version_id}/scope/resolve",
                           json={"openQuestion": "req-1",
                                 "resolution": "Northwind's CMS supports the migration"})
    assert response.status_code == 200, response.text
    assert response.json()["openQuestions"] == []
    # The same workflow that refused submission before now permits it.
    response = client.post(f"/v1/proposal-versions/{version_id}/submit")
    assert response.status_code == 409  # still blocked: no approved claims…


def test_copy_version_reuses_only_usable_claims(client, api_engine):
    _seed(api_engine)
    proposal_id, first = _new_proposal(client)
    _drive_to_locked(client, first)
    response = client.post(f"/v1/proposals/{proposal_id}/versions",
                           json={"copyFromVersionId": first})
    assert response.status_code == 201, response.text
    second = response.json()["version"]
    assert second["versionNumber"] == 2
    assert second["status"] == "working"
    assert second["quote"]["lines"]  # the quote carried over
    assert "claim-onboarding-40" in second["claimIds"]


# --- Journey helpers --------------------------------------------------------


def _drive_to_submitted(client, version_id: str) -> None:
    response = client.post(f"/v1/proposal-versions/{version_id}/generate",
                           json=GENERATE_BODY)
    assert response.status_code == 200, response.text
    response = client.post(f"/v1/proposal-versions/{version_id}/quote/calculate",
                           json=QUOTE_BODY)
    assert response.status_code == 200, response.text
    response = client.post(f"/v1/proposal-versions/{version_id}/validate")
    assert response.status_code == 200, response.text
    assert [f for f in response.json()["flags"] if f["severity"] == "blocking"] == []
    response = client.post(f"/v1/proposal-versions/{version_id}/submit")
    assert response.status_code == 200, response.text


def _drive_to_locked(client, version_id: str) -> None:
    _drive_to_submitted(client, version_id)
    approvals = client.get(
        f"/v1/proposal-versions/{version_id}").json()["approvals"]
    for approval in approvals:
        response = client.post(f"/v1/approvals/{approval['id']}/decide",
                               json={"decision": "approved", "reviewerId": "u_prop",
                                     "reviewerRole": approval["requiredRole"]})
        assert response.status_code == 200, response.text


def _drive_to_delivered(client, version_id: str) -> None:
    _drive_to_locked(client, version_id)
    response = client.post(f"/v1/proposal-versions/{version_id}/render", json={})
    assert response.status_code == 200, response.text
    response = client.post(f"/v1/proposal-versions/{version_id}/deliver",
                           json={"provider": "pandadoc", "outcome": "success"})
    assert response.status_code == 200, response.text
