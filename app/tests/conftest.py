"""Shared fixtures. Versions and quotes are built from the real models and the
real pricing engine, never hand-written dicts, so a contract change breaks the
fixtures rather than letting stale shapes pass."""

from decimal import Decimal

import pytest

from app.domain.pricing import calculate_quote
from app.domain.schemas import (
    Approval,
    Assumption,
    Deliverable,
    Milestone,
    PricingRule,
    ProposalVersion,
    Scope,
)

NOW = "2026-08-01T10:00:00Z"


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
