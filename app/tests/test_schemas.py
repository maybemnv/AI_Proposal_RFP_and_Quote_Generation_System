import pydantic
import pytest

from app.domain.schemas import (
    PROVIDERS,
    VALIDATION_FLAG_CODES,
    Approval,
    Claim,
    GenerateDraftRequest,
    ProposalVersion,
    Quote,
    QuoteLine,
    SourceRecord,
    ValidationFlag,
)


def test_all_eight_prd_providers_are_accepted():
    assert set(PROVIDERS) == {
        "hubspot", "salesforce", "pandadoc", "docusign", "stripe",
        "google_drive", "microsoft_365", "manual",
    }
    for provider in PROVIDERS:
        record = SourceRecord.model_validate({
            "id": "s1", "provider": provider, "title": "t",
            "retrievedAt": "2026-08-01T09:00:00Z", "contentHash": "abc",
            "sourceType": "discovery", "approvedForGeneration": True,
        })
        assert record.provider == provider


def test_unknown_provider_is_rejected():
    with pytest.raises(pydantic.ValidationError):
        SourceRecord.model_validate({
            "id": "s1", "provider": "notion", "title": "t",
            "retrievedAt": "2026-08-01T09:00:00Z", "contentHash": "abc",
            "sourceType": "discovery", "approvedForGeneration": True,
        })


def test_source_record_camelcase_roundtrip():
    record = SourceRecord.model_validate({
        "id": "1", "provider": "hubspot", "title": "Discovery notes",
        "retrievedAt": "2026-08-01T09:00:00Z", "contentHash": "abc",
        "sourceType": "discovery", "approvedForGeneration": True,
    })
    assert record.content_hash == "abc"
    assert record.approved_for_generation is True
    assert record.uri is None
    dumped = record.model_dump(by_alias=True)
    assert "contentHash" in dumped and "content_hash" not in dumped
    assert "approvedForGeneration" in dumped


def test_snake_case_construction_also_works():
    record = SourceRecord(
        id="1", provider="manual", title="t", retrieved_at="2026-08-01T09:00:00Z",
        content_hash="abc", source_type="manual", approved_for_generation=False,
    )
    assert record.model_dump(by_alias=True)["sourceType"] == "manual"


def test_validation_flag_codes_match_the_prd():
    assert set(VALIDATION_FLAG_CODES) == {
        "MISSING_SOURCE", "UNAPPROVED_CLAIM", "EXPIRED_CLAIM", "UNRESOLVED_REQUIREMENT",
        "PRICE_MISMATCH", "MISSING_APPROVAL", "SCHEMA_ERROR", "RENDER_ERROR",
    }


def test_validation_flag_rejects_bad_severity():
    with pytest.raises(pydantic.ValidationError):
        ValidationFlag.model_validate({
            "code": "MISSING_SOURCE", "severity": "urgent", "message": "x",
            "relatedIds": [],
        })


def test_quote_has_no_status_field_per_the_canonical_contract():
    assert "status" not in Quote.model_fields


def test_quote_money_fields_are_integers():
    line = QuoteLine(
        id="l1", label="Strategy", rule_id="r1", quantity=2,
        unit_price_minor=120000, subtotal_minor=240000, optional=False,
        selected=True, source_record_ids=[],
    )
    quote = Quote(
        currency="USD", lines=[line], subtotal_minor=240000, discount_minor=0,
        tax_minor=0, total_minor=240000, payment_schedule=[],
        pricing_rule_version="2026.1", input_hash="h",
        calculated_at="2026-08-01T00:00:00Z",
    )
    for value in (quote.subtotal_minor, quote.total_minor, line.unit_price_minor):
        assert isinstance(value, int)


def test_claim_status_literal_is_enforced():
    claim = Claim(id="c1", text="t", status="approved", source_record_ids=["s1"],
                  allowed_contexts=[], prohibited_contexts=[])
    assert claim.status == "approved"
    with pytest.raises(pydantic.ValidationError):
        Claim(id="c1", text="t", status="maybe", source_record_ids=["s1"],
              allowed_contexts=[], prohibited_contexts=[])


def test_approval_role_and_kind_literals():
    approval = Approval.model_validate({
        "id": "a1", "proposalVersionId": "v1", "kind": "quote",
        "requiredRole": "quote_approver", "decision": "pending",
    })
    assert approval.required_role == "quote_approver"
    with pytest.raises(pydantic.ValidationError):
        Approval.model_validate({
            "id": "a1", "proposalVersionId": "v1", "kind": "quote",
            "requiredRole": "admin", "decision": "pending",
        })


def _version_payload(status: str) -> dict:
    return {
        "id": "v1", "proposalId": "p1", "versionNumber": 1, "status": status,
        "title": "t",
        "scope": {"deliverables": [], "milestones": [], "assumptions": [],
                  "exclusions": [], "openQuestions": []},
        "quote": {"currency": "USD", "lines": [], "subtotalMinor": 0,
                  "discountMinor": 0, "taxMinor": 0, "totalMinor": 0,
                  "paymentSchedule": [], "pricingRuleVersion": "2026.1",
                  "inputHash": "h", "calculatedAt": "2026-08-01T00:00:00Z"},
        "claimIds": [], "sourceRecordIds": [], "unresolvedFlags": [],
        "createdAt": "2026-08-01T00:00:00Z",
    }


def test_proposal_version_status_literal():
    assert ProposalVersion.model_validate(_version_payload("locked")).status == "locked"
    with pytest.raises(pydantic.ValidationError) as err:
        ProposalVersion.model_validate(_version_payload("open"))
    assert "status" in str(err.value)


def test_generate_draft_request_section_keys():
    with pytest.raises(pydantic.ValidationError):
        GenerateDraftRequest.model_validate({
            "proposalVersionId": "v1", "templateId": "t1",
            "requestedSections": ["conclusion"],
            "modelProvider": "claude", "modelName": "claude-opus-5",
        })


def test_extra_fields_are_forbidden():
    with pytest.raises(pydantic.ValidationError):
        SourceRecord.model_validate({
            "id": "1", "provider": "hubspot", "title": "t",
            "retrievedAt": "2026-08-01T09:00:00Z", "contentHash": "abc",
            "sourceType": "discovery", "approvedForGeneration": True,
            "unexpected": "field",
        })
