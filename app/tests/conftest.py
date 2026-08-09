"""Shared fixtures. Versions and quotes are built from the real models and the
real pricing engine, never hand-written dicts, so a contract change breaks the
fixtures rather than letting stale shapes pass."""

from decimal import Decimal

import pytest

from app.domain.pricing import calculate_quote
from app.domain.schemas import (
    SECTION_KEYS,
    Approval,
    ApprovedClaim,
    Assumption,
    Deliverable,
    DiscoveryInput,
    EvidenceLink,
    GeneratedBlock,
    GenerateDraftRequest,
    GeneratedSection,
    Milestone,
    Opportunity,
    PricingRule,
    ProposalVersion,
    Requirement,
    Scope,
)
from app.persistence.models import create_all
from app.persistence.session import get_engine

NOW = "2026-08-01T10:00:00Z"


@pytest.fixture
def engine():
    """In-memory SQLite. Fast, and disposable per test."""
    eng = get_engine("sqlite+pysqlite:///:memory:")
    create_all(eng)
    return eng



@pytest.fixture
def consulting_rule() -> PricingRule:
    return PricingRule(
        id="rule-senior-day", version="2026.1", label="Senior consulting",
        unit="day", currency="USD", unit_price_minor=120000, min_quantity=1,
        max_quantity=60, optional=False, active_from="2026-01-01",
        active_until=None, discount_policy_id="policy-standard",
        source_record_ids=["src-rate-card"],
    )


@pytest.fixture
def sample_scope() -> Scope:
    return Scope(
        deliverables=[Deliverable(
            id="d1", name="Discovery workshop series", description="Four facilitated sessions",
            quantity=4, unit="workshop", milestone_ids=["m1"],
            source_record_ids=["src-notes"], optional=False,
        )],
        milestones=[Milestone(
            id="m1", name="Discovery complete", sequence=1,
            target_description="Findings accepted by the steering group",
            source_record_ids=["src-notes"],
        )],
        assumptions=[Assumption(
            id="a1", text="Client provides two subject-matter experts per session",
            source_record_ids=["src-notes"], customer_confirmation_required=True,
        )],
        exclusions=["Change management beyond the workshop series"],
        open_questions=[],
    )


@pytest.fixture
def sample_quote(consulting_rule):
    return calculate_quote(
        [{"id": "l1", "label": "Senior consulting", "ruleId": consulting_rule.id,
          "quantity": Decimal(10), "optional": False, "selected": True,
          "sourceRecordIds": ["src-rate-card"]}],
        {consulting_rule.id: consulting_rule},
        "USD",
        calculated_at=NOW,
    )


def _version(status, scope, quote, flags=()):
    return ProposalVersion(
        id="ver-1", proposal_id="prop-1", version_number=1, status=status,
        title="Customer onboarding acceleration", scope=scope, quote=quote,
        claim_ids=["claim-onboarding"], source_record_ids=["src-notes", "src-rate-card"],
        unresolved_flags=list(flags), created_at=NOW,
        locked_at=NOW if status in {"locked", "rendered", "delivered"} else None,
    )


@pytest.fixture
def working_version(sample_scope, sample_quote) -> ProposalVersion:
    return _version("working", sample_scope, sample_quote)


@pytest.fixture
def locked_version(sample_scope, sample_quote) -> ProposalVersion:
    return _version("locked", sample_scope, sample_quote)


@pytest.fixture
def locked_version_with_flag(sample_scope, sample_quote) -> ProposalVersion:
    return _version("locked", sample_scope, sample_quote, flags=["UNRESOLVED_REQUIREMENT"])


def _approval(id_, kind, role, decision):
    return Approval(
        id=id_, proposal_version_id="ver-1", kind=kind, required_role=role,
        decision=decision, reviewer_id="user-approver" if decision != "pending" else None,
        comment=None, decided_at=NOW if decision != "pending" else None,
    )


@pytest.fixture
def approvals_all_approved() -> list[Approval]:
    return [
        _approval("ap-quote", "quote", "quote_approver", "approved"),
        _approval("ap-proposal", "proposal", "proposal_approver", "approved"),
    ]


@pytest.fixture
def approvals_one_pending() -> list[Approval]:
    return [
        _approval("ap-quote", "quote", "quote_approver", "approved"),
        _approval("ap-proposal", "proposal", "proposal_approver", "pending"),
    ]


# --- generation -------------------------------------------------------------
# The four claim ids below are the ones the section fixtures cite. Task 13 seeds
# claims under these same ids; if the two ever drift, the generation tests fail
# rather than the demo.

CLAIM_IDS = (
    "claim-onboarding-40",
    "claim-time-to-value",
    "claim-csat-uplift",
    "claim-retention-2x",
)

CLAIM_TEXT = {
    "claim-onboarding-40": "Cut onboarding time by 40% for a comparable mid-size retailer",
    "claim-time-to-value": "Reduced time to first value from six weeks to three weeks",
    "claim-csat-uplift": "Post-onboarding CSAT rose from 3.8 to 4.5",
    "claim-retention-2x": "Achieved a 2x improvement in 90-day retention",
}


def _approved_claim(claim_id: str, status: str = "approved", **overrides) -> ApprovedClaim:
    payload = {
        "id": claim_id,
        "text": CLAIM_TEXT[claim_id],
        "status": status,
        "source_record_ids": ["src-case-northwind"],
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_until": "2027-01-01T00:00:00Z",
        "allowed_contexts": ["executive_summary", "case_studies"],
        "prohibited_contexts": [],
        "evidence": [EvidenceLink(
            claim_id=claim_id, source_record_id="src-case-northwind",
            locator="page 2", excerpt=CLAIM_TEXT[claim_id],
            verified_by="user-approver", verified_at=NOW,
        )],
    }
    payload.update(overrides)
    return ApprovedClaim(**payload)


@pytest.fixture
def northwind_opportunity() -> Opportunity:
    return Opportunity(
        id="opp-northwind", external_provider="hubspot", external_id="hs-9001",
        account_name="Northwind Retail", contact_name="R. Ortega",
        title="Customer onboarding acceleration", currency="USD", status="normalized",
        source_record_ids=["src-crm-hs-9001"], required_field_errors=[],
        imported_at="2026-08-01T09:00:00Z",
    )


def _draft_request(claims, sections, opportunity, scope) -> GenerateDraftRequest:
    return GenerateDraftRequest(
        proposal_version_id="ver-1",
        opportunity=opportunity,
        discovery=[DiscoveryInput(
            id="disc-1", opportunity_id=opportunity.id, kind="notes",
            text="Onboarding runs six weeks today. Target is three.",
            source_record_id="src-crm-hs-9001-notes", extracted_at=NOW,
        )],
        requirements=[Requirement(
            id="req-1", text="Complete four facilitated discovery workshops",
            source_record_ids=["src-notes-manual"], status="confirmed",
            confidence="high",
        )],
        scope=scope,
        approved_claims=claims,
        template_id="tmpl-consulting-v1",
        requested_sections=list(sections),
        model_provider="claude",
        model_name="claude-opus-5",
    )


ALL_SECTIONS = SECTION_KEYS


@pytest.fixture
def draft_request(northwind_opportunity, sample_scope) -> GenerateDraftRequest:
    return _draft_request(
        [_approved_claim(c) for c in CLAIM_IDS],
        ALL_SECTIONS, northwind_opportunity, sample_scope,
    )


@pytest.fixture
def draft_request_with_pending_claim(
    northwind_opportunity, sample_scope
) -> GenerateDraftRequest:
    """Every claim the fixtures cite is pending, so no assertion has a usable claim."""
    return _draft_request(
        [_approved_claim(c, status="pending_approval") for c in CLAIM_IDS],
        ALL_SECTIONS, northwind_opportunity, sample_scope,
    )


@pytest.fixture
def draft_request_with_expired_claim(
    northwind_opportunity, sample_scope
) -> GenerateDraftRequest:
    """Approved, but the validity window closed before NOW — I7."""
    return _draft_request(
        [_approved_claim(c, valid_until="2026-02-01T00:00:00Z") for c in CLAIM_IDS],
        ALL_SECTIONS, northwind_opportunity, sample_scope,
    )


# --- validation -------------------------------------------------------------
# validate_version takes a wide bundle because it is the single chokepoint for
# I8 — every blocking condition has to be visible to it at once. These fixtures
# assemble that bundle from the real models and the real pricing engine, so the
# clean case is clean because it recomputes, not because it was declared so.

CITED_CLAIM = "claim-onboarding-40"


def _sections() -> list[GeneratedSection]:
    """One block that asserts and cites, one that neither asserts nor cites."""
    return [GeneratedSection(key="executive_summary", blocks=[
        GeneratedBlock(
            block_id="executive_summary-1",
            content="The programme reduced onboarding time by 40% at a comparable retailer.",
            claim_ids=[CITED_CLAIM], source_record_ids=["src-case-northwind"],
        ),
        GeneratedBlock(
            block_id="executive_summary-2",
            content="The workshop series runs over four weeks against your steering cadence.",
            source_record_ids=["src-notes-manual"],
        ),
    ])]


def _requirements(status="confirmed", confidence="high") -> list[Requirement]:
    return [Requirement(
        id="req-1", text="Complete four facilitated discovery workshops",
        source_record_ids=["src-notes-manual"], status=status, confidence=confidence,
    )]


@pytest.fixture
def rogue_sections() -> list[GeneratedSection]:
    """An assertion with no claim behind it — what I1 exists to catch."""
    return [GeneratedSection(key="case_studies", blocks=[GeneratedBlock(
        block_id="case_studies-1",
        content="We reduced onboarding effort by 90% across every client.",
        source_record_ids=["src-notes-manual"],
    )])]


@pytest.fixture
def low_confidence_requirements() -> list[Requirement]:
    return _requirements(confidence="low")


# --- documents --------------------------------------------------------------


@pytest.fixture
def sections() -> list[GeneratedSection]:
    return _sections()


@pytest.fixture
def claims_by_id() -> dict:
    return {CITED_CLAIM: _approved_claim(CITED_CLAIM)}


@pytest.fixture
def evidence_by_claim() -> dict:
    return {CITED_CLAIM: _approved_claim(CITED_CLAIM).evidence}


@pytest.fixture
def version_with_optional_line(consulting_rule, sample_scope) -> ProposalVersion:
    """One selected line and one optional line left unselected.

    I4 on the page: the optional line is priced and labelled, and the total is
    the selected line alone.
    """
    optional_rule = consulting_rule.model_copy(update={
        "id": "rule-change-management", "label": "Change management support",
        "optional": True,
    })
    quote = calculate_quote(
        [{"id": "l1", "label": "Senior consulting", "ruleId": consulting_rule.id,
          "quantity": Decimal(10), "optional": False, "selected": True,
          "sourceRecordIds": ["src-rate-card"]},
         {"id": "l2", "label": "Change management support", "ruleId": optional_rule.id,
          "quantity": Decimal(5), "optional": True, "selected": False,
          "sourceRecordIds": ["src-rate-card"]}],
        {consulting_rule.id: consulting_rule, optional_rule.id: optional_rule},
        "USD",
        calculated_at=NOW,
    )
    return _version("locked", sample_scope, quote)


@pytest.fixture
def rejected_approval() -> list[Approval]:
    return [
        _approval("ap-quote", "quote", "quote_approver", "approved"),
        _approval("ap-proposal", "proposal", "proposal_approver", "rejected"),
    ]


@pytest.fixture
def clean_bundle(locked_version, consulting_rule, approvals_all_approved) -> dict:
    return {
        "version": locked_version,
        "sections": _sections(),
        "claims_by_id": {CITED_CLAIM: _approved_claim(CITED_CLAIM)},
        "evidence_by_claim": {CITED_CLAIM: _approved_claim(CITED_CLAIM).evidence},
        "rules": {consulting_rule.id: consulting_rule},
        "requirements": _requirements(),
        "approvals": approvals_all_approved,
        "document_status": "ready",
        "now": NOW,
    }


@pytest.fixture
def bundle_with_open_question(clean_bundle) -> dict:
    return dict(clean_bundle) | {"requirements": _requirements(status="open_question")}


@pytest.fixture
def bundle_with_assumption(clean_bundle) -> dict:
    return dict(clean_bundle) | {"requirements": _requirements(status="assumption")}


@pytest.fixture
def bundle_with_pending_approval(clean_bundle, approvals_one_pending) -> dict:
    return dict(clean_bundle) | {"approvals": approvals_one_pending}


@pytest.fixture
def bundle_with_expired_claim(clean_bundle) -> dict:
    expired = _approved_claim(CITED_CLAIM, valid_until="2026-02-01T00:00:00Z")
    return dict(clean_bundle) | {"claims_by_id": {CITED_CLAIM: expired}}
