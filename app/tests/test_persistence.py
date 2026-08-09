import pytest

from app.domain.workflow import TransitionError, content_hash
from app.persistence.models import Base, ProposalVersionRow, create_all
from app.persistence.repositories import (
    ApprovalRepo,
    ClaimRepo,
    OpportunityRepo,
    PricingRuleRepo,
    VersionRepo,
)
from app.persistence.session import get_engine, session_scope


@pytest.fixture
def engine():
    eng = get_engine("sqlite+pysqlite:///:memory:")
    create_all(eng)
    return eng


def test_version_roundtrips_through_the_database(engine, working_version):
    with session_scope(engine) as s:
        VersionRepo(s).add(working_version)
    with session_scope(engine) as s:
        loaded = VersionRepo(s).get(working_version.id)
    assert loaded.quote.total_minor == working_version.quote.total_minor
    assert loaded.scope.deliverables[0].name == working_version.scope.deliverables[0].name
    assert loaded.quote.lines[0].rule_id == working_version.quote.lines[0].rule_id
    assert loaded.claim_ids == working_version.claim_ids
    assert loaded.locked_at is None


def test_stored_version_equals_the_original_model(engine, working_version):
    with session_scope(engine) as s:
        VersionRepo(s).add(working_version)
    with session_scope(engine) as s:
        assert VersionRepo(s).get(working_version.id) == working_version


def test_locked_version_update_is_refused(engine, locked_version):
    with session_scope(engine) as s:
        VersionRepo(s).add(locked_version)
    with session_scope(engine) as s, pytest.raises(TransitionError, match="locked"):
        VersionRepo(s).update(locked_version.model_copy(update={"title": "changed"}))


def test_immutability_is_judged_by_stored_status_not_the_incoming_model(engine, locked_version):
    """Sending status='working' must not launder a locked row into a mutable one."""
    with session_scope(engine) as s:
        VersionRepo(s).add(locked_version)
    with session_scope(engine) as s:
        forged = locked_version.model_copy(update={"status": "working", "title": "changed"})
        with pytest.raises(TransitionError, match="locked"):
            VersionRepo(s).update(forged)
    with session_scope(engine) as s:
        assert VersionRepo(s).get(locked_version.id).title == locked_version.title


def test_working_version_updates_normally(engine, working_version):
    with session_scope(engine) as s:
        VersionRepo(s).add(working_version)
    with session_scope(engine) as s:
        VersionRepo(s).update(working_version.model_copy(update={"title": "Revised title"}))
    with session_scope(engine) as s:
        assert VersionRepo(s).get(working_version.id).title == "Revised title"


def test_promote_is_the_only_path_that_moves_a_locked_version(engine, locked_version):
    with session_scope(engine) as s:
        VersionRepo(s).add(locked_version)
    with session_scope(engine) as s:
        VersionRepo(s).promote(locked_version, "rendered")
    with session_scope(engine) as s:
        assert VersionRepo(s).get(locked_version.id).status == "rendered"


def test_promote_still_refuses_an_illegal_transition(engine, locked_version):
    with session_scope(engine) as s:
        VersionRepo(s).add(locked_version)
    with session_scope(engine) as s, pytest.raises(TransitionError):
        VersionRepo(s).promote(locked_version, "working")


def test_promote_to_locked_stamps_the_content_hash(engine, working_version):
    submitted = working_version.model_copy(update={"status": "submitted"})
    with session_scope(engine) as s:
        VersionRepo(s).add(submitted)
    locked = submitted.model_copy(
        update={"status": "locked", "locked_at": "2026-08-02T09:00:00Z"})
    with session_scope(engine) as s:
        VersionRepo(s).promote(locked, "locked")
    with session_scope(engine) as s:
        row = s.get(ProposalVersionRow, submitted.id)
        assert row.content_hash == content_hash(locked)
        assert row.locked_at == "2026-08-02T09:00:00Z"


def test_get_missing_version_raises_keyerror(engine):
    with session_scope(engine) as s, pytest.raises(KeyError):
        VersionRepo(s).get("nope")


def test_list_versions_filters_by_proposal(engine, working_version):
    other = working_version.model_copy(update={"id": "ver-2", "proposal_id": "prop-2"})
    with session_scope(engine) as s:
        VersionRepo(s).add(working_version)
        VersionRepo(s).add(other)
    with session_scope(engine) as s:
        found = VersionRepo(s).list(proposal_id="prop-1")
    assert [v.id for v in found] == ["ver-1"]


def test_total_minor_is_denormalized_for_list_views(engine, working_version):
    with session_scope(engine) as s:
        VersionRepo(s).add(working_version)
    with session_scope(engine) as s:
        row = s.get(ProposalVersionRow, working_version.id)
        assert row.total_minor == working_version.quote.total_minor
        assert isinstance(row.total_minor, int)


def test_other_repositories_roundtrip(engine, consulting_rule, approvals_all_approved):
    from app.domain.schemas import Claim, Opportunity

    opp = Opportunity(
        id="opp-1", external_provider="hubspot", external_id="hs-9001",
        account_name="Northwind Retail", contact_name="R. Ortega",
        title="Customer onboarding acceleration", currency="USD", status="normalized",
        source_record_ids=["src-crm"], required_field_errors=[],
        imported_at="2026-08-01T09:00:00Z",
    )
    claim = Claim(id="claim-1", text="Cut onboarding time 40%", status="approved",
                  source_record_ids=["src-case"], allowed_contexts=["case_studies"],
                  prohibited_contexts=[])
    with session_scope(engine) as s:
        OpportunityRepo(s).add(opp)
        ClaimRepo(s).add(claim)
        PricingRuleRepo(s).add(consulting_rule)
        for approval in approvals_all_approved:
            ApprovalRepo(s).add(approval)
    with session_scope(engine) as s:
        assert OpportunityRepo(s).get("opp-1") == opp
        assert ClaimRepo(s).get("claim-1") == claim
        assert PricingRuleRepo(s).get(consulting_rule.id) == consulting_rule
        assert len(ApprovalRepo(s).list(proposal_version_id="ver-1")) == 2


def test_base_metadata_covers_every_table(engine):
    expected = {
        "source_records", "opportunities", "discovery_inputs", "requirements",
        "proposals", "proposal_versions", "generated_sections", "claims",
        "evidence_links", "pricing_rules", "discount_policies", "approvals",
        "documents", "engagement_records", "audit_events",
    }
    assert expected <= set(Base.metadata.tables)
