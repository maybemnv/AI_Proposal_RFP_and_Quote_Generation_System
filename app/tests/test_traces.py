import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.api.main import create_app
from app.cli import seed_all
from app.domain.claims import contains_verifiable_assertion
from app.domain.schemas import Opportunity
from app.persistence.models import create_all
from app.persistence.repositories import OpportunityRepo
from app.persistence.session import session_scope
from app.tests.test_api import NOW, _StubRenderer

TRACE_A_QUOTE_REQUEST = {
    "currency": "USD", "discountMinor": 0, "taxMinor": 0,
    "lines": [
        {"id": "line_strategy", "label": "Strategy days", "ruleId": "rule_strategy_day", "quantity": "4", "optional": False, "selected": True, "sourceRecordIds": ["src-agency-ratecard"]},
        {"id": "line_design", "label": "Design sprint", "ruleId": "rule_design_sprint", "quantity": "1", "optional": False, "selected": True, "sourceRecordIds": ["src-agency-ratecard"]},
        {"id": "line_build", "label": "Build week", "ruleId": "rule_build_week", "quantity": "1", "optional": False, "selected": True, "sourceRecordIds": ["src-agency-ratecard"]},
        {"id": "line_training", "label": "Training session", "ruleId": "rule_training", "quantity": "1", "optional": True, "selected": False, "sourceRecordIds": ["src-agency-ratecard"]},
    ],
    "installments": [
        {"sequence": 1, "label": "Deposit", "amountMinor": 615000, "dueDescription": "On signature"},
        {"sequence": 2, "label": "Final", "amountMinor": 615000, "dueDescription": "On delivery"},
    ],
}

TRACE_B_QUOTE_REQUEST = {
    "currency": "USD", "discountMinor": 0, "taxMinor": 0,
    "lines": [{"id": "line_rfp", "label": "Response days", "ruleId": "rule_strategy_day", "quantity": "2", "optional": False, "selected": True, "sourceRecordIds": ["src-rfp-response"]}],
    "installments": [
        {"sequence": 1, "label": "Deposit", "amountMinor": 120000, "dueDescription": "On signature"},
        {"sequence": 2, "label": "Final", "amountMinor": 120000, "dueDescription": "On delivery"},
    ],
}


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


@pytest.fixture
def seed(api_engine):
    with session_scope(api_engine) as session:
        return seed_all(session)


def _create_version(client, opportunity_id: str) -> str:
    response = client.post("/v1/proposals", json={"opportunityId": opportunity_id})
    assert response.status_code == 201, response.text
    return response.json()["version"]["id"]


def _approve_all(client, version_id: str) -> None:
    for approval in client.get(f"/v1/proposal-versions/{version_id}").json()["approvals"]:
        response = client.post(f"/v1/approvals/{approval['id']}/decide", json={
            "decision": "approved", "reviewerId": f"user_{approval['requiredRole']}",
            "reviewerRole": approval["requiredRole"],
        })
        assert response.status_code == 200, response.text


def _build_delivered(client, opportunity_id="opp_northwind") -> dict:
    version_id = _create_version(client, opportunity_id)
    scope = client.post(f"/v1/proposal-versions/{version_id}/scope/extract")
    assert scope.status_code == 200, scope.text
    if scope.json()["openQuestions"]:
        resolved = client.post(f"/v1/proposal-versions/{version_id}/scope/resolve", json={
            "openQuestion": scope.json()["openQuestions"][0],
            "resolution": "Legacy CMS stays on v4 through Q4.",
        })
        assert resolved.status_code == 200, resolved.text
    quote = client.post(f"/v1/proposal-versions/{version_id}/quote/calculate", json=TRACE_A_QUOTE_REQUEST)
    assert quote.status_code == 200, quote.text
    draft = client.post(f"/v1/proposal-versions/{version_id}/generate", json={
        "templateId": "tpl-agency", "requestedSections": [
            "executive_summary", "understanding", "scope", "milestones", "assumptions",
            "options", "pricing", "payment_schedule", "case_studies", "next_steps",
        ], "modelProvider": "claude", "modelName": "claude-opus-5",
    })
    assert draft.status_code == 200, draft.text
    validate = client.post(f"/v1/proposal-versions/{version_id}/validate")
    assert validate.status_code == 200, validate.text
    assert not [flag for flag in validate.json()["flags"] if flag["severity"] == "blocking"]
    submitted = client.post(f"/v1/proposal-versions/{version_id}/submit")
    assert submitted.status_code == 200, submitted.text
    _approve_all(client, version_id)
    rendered = client.post(f"/v1/proposal-versions/{version_id}/render", json={})
    assert rendered.status_code == 200, rendered.text
    delivered = client.post(f"/v1/proposal-versions/{version_id}/deliver", json={"provider": "pandadoc", "outcome": "success"})
    assert delivered.status_code == 200, delivered.text
    return client.get(f"/v1/proposal-versions/{version_id}").json()


@pytest.fixture
def delivered_bundle(client, seed):
    version = _build_delivered(client)
    with session_scope(client.app.state.engine) as session:
        claims = {claim.id: claim for claim in __import__("app.persistence.repositories", fromlist=["ClaimRepo"]).ClaimRepo(session).list()}
        evidence = __import__("app.persistence.repositories", fromlist=["EvidenceRepo"]).EvidenceRepo(session).by_claim(list(claims))
        rules = {rule.id: rule for rule in __import__("app.persistence.repositories", fromlist=["PricingRuleRepo"]).PricingRuleRepo(session).list()}
    return {"version": version, "sections": version["sections"], "claims": claims, "evidence": evidence, "rules": rules, "approvals": version["approvals"], "document": version["document"]}


def test_i1_every_client_facing_claim_is_backed(delivered_bundle):
    for section in delivered_bundle["sections"]:
        for block in section["blocks"]:
            if contains_verifiable_assertion(block["content"]):
                assert block["claimIds"]
                for claim_id in block["claimIds"]:
                    assert delivered_bundle["claims"][claim_id].status == "approved"
                    assert delivered_bundle["evidence"][claim_id]


def test_i2_every_quote_line_references_one_rule_version(delivered_bundle):
    versions = {delivered_bundle["rules"][line["ruleId"]].version for line in delivered_bundle["version"]["quote"]["lines"]}
    assert len(versions) == 1


def test_i3_total_formula_holds(delivered_bundle):
    quote = delivered_bundle["version"]["quote"]
    assert quote["totalMinor"] == quote["subtotalMinor"] - quote["discountMinor"] + quote["taxMinor"]


def test_i4_unselected_optional_lines_are_excluded(delivered_bundle):
    quote = delivered_bundle["version"]["quote"]
    assert quote["subtotalMinor"] == sum(line["subtotalMinor"] for line in quote["lines"] if line["selected"])


def test_i5_locked_version_cannot_change(client, delivered_bundle):
    version_id = delivered_bundle["version"]["id"]
    for path, body in [("generate", {}), ("quote/calculate", {}), ("validate", {})]:
        assert client.post(f"/v1/proposal-versions/{version_id}/{path}", json=body).status_code == 409


def test_i6_delivery_required_a_ready_document_and_every_approval(delivered_bundle):
    assert delivered_bundle["document"]["status"] == "ready"
    assert all(approval["decision"] == "approved" for approval in delivered_bundle["approvals"])


def test_i7_expired_or_rejected_claims_cannot_enter_a_new_version(client, delivered_bundle):
    version = delivered_bundle["version"]
    response = client.post(f"/v1/proposals/{version['proposalId']}/versions", json={"copyFromVersionId": version["id"]})
    assert response.status_code == 201, response.text
    copied = response.json().get("version", response.json())
    assert "claim-legacy-cms" not in copied["claimIds"]
    assert copied["versionNumber"] == version["versionNumber"] + 1


def test_i8_each_blocking_condition_blocks_delivery(client, seed):
    version_id = _create_version(client, "opp_northwind")
    response = client.post(f"/v1/proposal-versions/{version_id}/deliver", json={})
    assert response.status_code == 409
    scope = client.post(f"/v1/proposal-versions/{version_id}/scope/extract")
    assert scope.status_code == 200
    assert client.post(f"/v1/proposal-versions/{version_id}/deliver", json={}).status_code == 409


def test_i9_no_float_appears_in_any_money_field(delivered_bundle):
    quote = delivered_bundle["version"]["quote"]
    values = [quote["subtotalMinor"], quote["discountMinor"], quote["taxMinor"], quote["totalMinor"], *[line["subtotalMinor"] for line in quote["lines"]], *[line["unitPriceMinor"] for line in quote["lines"]], *[item["amountMinor"] for item in quote["paymentSchedule"]]]
    assert all(isinstance(value, int) and not isinstance(value, bool) for value in values)


def test_i10_provider_events_append_and_never_mutate(client, delivered_bundle):
    version_id = delivered_bundle["version"]["id"]
    before = client.get(f"/v1/proposal-versions/{version_id}").json()
    response = client.post("/v1/engagement/webhook", json={"provider": "docusign", "type": "signed", "proposalVersionId": version_id, "at": "2026-08-03T09:00:00Z"})
    assert response.status_code == 201
    assert client.get(f"/v1/proposal-versions/{version_id}").json() == before


def test_trace_a_end_to_end(client, seed):
    imported = client.post("/v1/opportunities/import", json={"provider": "hubspot", "externalId": "42", "outcome": "success", "fixture": "agency_discovery"})
    assert imported.status_code == 201, imported.text
    assert imported.json()["status"] == "normalized"
    version_id = _create_version(client, imported.json()["id"])
    attached = client.post(f"/v1/proposal-versions/{version_id}/discovery", json={"kind": "transcript", "sourceRecordId": "src_transcript"})
    assert attached.status_code == 200, attached.text
    scope = client.post(f"/v1/proposal-versions/{version_id}/scope/extract")
    assert len(scope.json()["deliverables"]) == 5
    assert scope.json()["openQuestions"]
    client.post(f"/v1/proposal-versions/{version_id}/scope/resolve", json={"openQuestion": scope.json()["openQuestions"][0], "resolution": "Legacy CMS stays on v4 through Q4."})
    quote = client.post(f"/v1/proposal-versions/{version_id}/quote/calculate", json=TRACE_A_QUOTE_REQUEST).json()
    assert quote["totalMinor"] == quote["subtotalMinor"] - quote["discountMinor"] + quote["taxMinor"]
    assert sum(item["amountMinor"] for item in quote["paymentSchedule"]) == quote["totalMinor"]
    draft = client.post(f"/v1/proposal-versions/{version_id}/generate", json={"templateId": "tpl-agency", "requestedSections": ["executive_summary", "understanding", "scope", "milestones", "assumptions", "options", "pricing", "payment_schedule", "case_studies", "next_steps"], "modelProvider": "claude", "modelName": "claude-opus-5"}).json()
    assert draft["sections"][0]["key"] == "executive_summary"
    assert not [flag for flag in client.post(f"/v1/proposal-versions/{version_id}/validate").json()["flags"] if flag["severity"] == "blocking"]
    assert client.post(f"/v1/proposal-versions/{version_id}/submit").json()["status"] == "submitted"
    _approve_all(client, version_id)
    assert client.get(f"/v1/proposal-versions/{version_id}").json()["status"] == "locked"
    assert client.post(f"/v1/proposal-versions/{version_id}/render", json={}).json()["status"] == "rendered"
    final = client.post(f"/v1/proposal-versions/{version_id}/deliver", json={"provider": "pandadoc", "outcome": "success"})
    assert final.status_code == 200
    assert final.json()["status"] == "delivered"
    assert final.json()["document"]["status"] == "ready"


def test_trace_a_missing_source_blocks_generation(client, seed):
    with session_scope(client.app.state.engine) as session:
        OpportunityRepo(session).add(Opportunity(id="opp_empty", external_provider="manual", external_id="empty", account_name="Empty", title="No sources", currency="USD", status="normalized", source_record_ids=[], required_field_errors=[], imported_at=NOW))
    version_id = _create_version(client, "opp_empty")
    response = client.post(f"/v1/proposal-versions/{version_id}/generate", json={})
    assert response.status_code == 409
    assert any(flag["code"] == "MISSING_SOURCE" for flag in response.json()["flags"])


def test_trace_a_over_policy_discount_requires_quote_approval(client, seed):
    version_id = _create_version(client, "opp_northwind")
    quote_request = {**TRACE_A_QUOTE_REQUEST, "discountMinor": 900000, "installments": [
        {"sequence": 1, "label": "Deposit", "amountMinor": 165000, "dueDescription": "On signature"},
        {"sequence": 2, "label": "Final", "amountMinor": 165000, "dueDescription": "On delivery"},
    ]}
    quote = client.post(f"/v1/proposal-versions/{version_id}/quote/calculate", json=quote_request).json()
    assert quote["status"] == "review_required"
    submitted = client.post(f"/v1/proposal-versions/{version_id}/submit")
    assert submitted.status_code == 409 or any(item["kind"] == "quote" for item in submitted.json().get("approvals", []))


def test_trace_a_failed_render_blocks_delivery(client, seed):
    # Prepare a fresh clean locked version for the failure branch.
    version_id = _create_version(client, "opp_northwind")
    scope = client.post(f"/v1/proposal-versions/{version_id}/scope/extract")
    assert scope.status_code == 200, scope.text
    if scope.json()["openQuestions"]:
        resolved = client.post(f"/v1/proposal-versions/{version_id}/scope/resolve", json={
            "openQuestion": scope.json()["openQuestions"][0],
            "resolution": "Legacy CMS stays on v4 through Q4.",
        })
        assert resolved.status_code == 200, resolved.text
    quote = client.post(f"/v1/proposal-versions/{version_id}/quote/calculate", json=TRACE_A_QUOTE_REQUEST)
    assert quote.status_code == 200, quote.text
    draft = client.post(f"/v1/proposal-versions/{version_id}/generate", json={
        "templateId": "tpl-agency", "requestedSections": [
            "executive_summary", "understanding", "scope", "milestones", "assumptions",
            "options", "pricing", "payment_schedule", "case_studies", "next_steps",
        ], "modelProvider": "claude", "modelName": "claude-opus-5",
    })
    assert draft.status_code == 200, draft.text
    validate = client.post(f"/v1/proposal-versions/{version_id}/validate")
    assert validate.status_code == 200, validate.text
    assert not [flag for flag in validate.json()["flags"] if flag["severity"] == "blocking"]
    submitted = client.post(f"/v1/proposal-versions/{version_id}/submit")
    assert submitted.status_code == 200, submitted.text
    _approve_all(client, version_id)
    failed = client.post(f"/v1/proposal-versions/{version_id}/render", json={"outcome": "failure"})
    assert failed.status_code == 200, failed.text
    assert failed.json()["status"] == "failed"
    delivery = client.post(f"/v1/proposal-versions/{version_id}/deliver", json={})
    assert delivery.status_code == 409
    assert any(flag["code"] == "RENDER_ERROR" for flag in delivery.json()["flags"])


def test_trace_b_end_to_end(client, seed):
    imported = client.post("/v1/opportunities/import", json={"provider": "manual", "outcome": "success", "fixture": "rfp_response"})
    assert imported.status_code == 201, imported.text
    version_id = _create_version(client, imported.json()["id"])
    assert client.post(f"/v1/proposal-versions/{version_id}/discovery", json={"kind": "rfp_text", "sourceRecordId": "src_rfp"}).status_code == 200
    assert len(client.post(f"/v1/proposal-versions/{version_id}/scope/extract").json()["deliverables"]) == 12
    assert client.post(f"/v1/proposal-versions/{version_id}/quote/calculate", json=TRACE_B_QUOTE_REQUEST).status_code == 200
    draft = client.post(f"/v1/proposal-versions/{version_id}/generate", json={"templateId": "tpl-rfp", "requestedSections": ["rfp_answers", "pricing"], "modelProvider": "claude", "modelName": "claude-opus-5"})
    assert draft.status_code == 200, draft.text
    assert not [flag for flag in client.post(f"/v1/proposal-versions/{version_id}/validate").json()["flags"] if flag["severity"] == "blocking"]
    assert client.post(f"/v1/proposal-versions/{version_id}/submit").status_code == 200
    _approve_all(client, version_id)
    client.post(f"/v1/proposal-versions/{version_id}/render", json={})
    assert client.post(f"/v1/proposal-versions/{version_id}/deliver", json={"provider": "docusign", "outcome": "success"}).json()["status"] == "delivered"


def test_trace_b_answers_follow_rfp_order(client, seed):
    imported = client.post("/v1/opportunities/import", json={"provider": "manual", "outcome": "success", "fixture": "rfp_response"}).json()
    version_id = _create_version(client, imported["id"])
    client.post(f"/v1/proposal-versions/{version_id}/discovery", json={"kind": "rfp_text", "sourceRecordId": "src_rfp"})
    client.post(f"/v1/proposal-versions/{version_id}/scope/extract")
    client.post(f"/v1/proposal-versions/{version_id}/quote/calculate", json=TRACE_B_QUOTE_REQUEST)
    client.post(f"/v1/proposal-versions/{version_id}/generate", json={"requestedSections": ["rfp_answers"]})
    answers = next(section for section in client.get(f"/v1/proposal-versions/{version_id}").json()["sections"] if section["key"] == "rfp_answers")
    numbers = [int(block["content"].split(".")[0]) for block in answers["blocks"]]
    assert numbers == list(range(1, 13))


def test_trace_b_every_answer_cites_a_source(client, seed):
    imported = client.post("/v1/opportunities/import", json={"provider": "manual", "outcome": "success", "fixture": "rfp_response"}).json()
    version_id = _create_version(client, imported["id"])
    client.post(f"/v1/proposal-versions/{version_id}/discovery", json={"kind": "rfp_text", "sourceRecordId": "src_rfp"})
    client.post(f"/v1/proposal-versions/{version_id}/scope/extract")
    client.post(f"/v1/proposal-versions/{version_id}/quote/calculate", json=TRACE_B_QUOTE_REQUEST)
    client.post(f"/v1/proposal-versions/{version_id}/generate", json={"requestedSections": ["rfp_answers"]})
    answers = next(section for section in client.get(f"/v1/proposal-versions/{version_id}").json()["sections"] if section["key"] == "rfp_answers")
    assert all(block["sourceRecordIds"] for block in answers["blocks"])
