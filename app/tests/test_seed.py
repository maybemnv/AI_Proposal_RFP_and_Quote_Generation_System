"""Contracts for the deterministic Trace A and Trace B demo seed."""

from app.cli import seed_all
from app.persistence.repositories import ClaimRepo, PricingRuleRepo, VersionRepo
from app.persistence.session import session_scope


def test_seed_produces_both_traces(engine):
    with session_scope(engine) as session:
        result = seed_all(session)
        assert len(result.opportunity_ids) == 2
        assert len(result.version_ids) == 2


def test_trace_a_has_an_open_question_and_a_pending_claim(engine):
    with session_scope(engine) as session:
        result = seed_all(session)
        version = VersionRepo(session).get(result.version_ids[0])
        assert version.scope.open_questions
        claims = ClaimRepo(session).list()
        assert any(claim.status == "pending_approval" for claim in claims)


def test_trace_b_requirements_preserve_rfp_order(engine):
    with session_scope(engine) as session:
        result = seed_all(session)
        version = VersionRepo(session).get(result.version_ids[1])
        numbers = [deliverable.name.split(".")[0] for deliverable in version.scope.deliverables]
        assert numbers == sorted(numbers, key=int)


def test_pricing_rules_share_one_version_and_currency(engine):
    with session_scope(engine) as session:
        seed_all(session)
        rules = PricingRuleRepo(session).list()
        assert len(rules) == 6
        assert {rule.version for rule in rules} == {"2026.1"}
        assert {rule.currency for rule in rules} == {"USD"}


def test_seed_is_idempotent(engine):
    with session_scope(engine) as session:
        first = seed_all(session)
        second = seed_all(session)
        assert first.opportunity_ids == second.opportunity_ids
        assert first.proposal_ids == second.proposal_ids
        assert first.version_ids == second.version_ids
