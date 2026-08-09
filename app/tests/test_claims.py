from app.domain.claims import (
    contains_verifiable_assertion,
    usable_in_new_version,
    validate_block,
)
from app.domain.schemas import Claim, EvidenceLink, GeneratedBlock

NOW = "2026-08-01"


def claim(status="approved", valid_until=None, id_="c1", valid_from=None):
    return Claim(id=id_, text="Cut onboarding time 40%", status=status,
                 source_record_ids=["s1"], valid_from=valid_from,
                 valid_until=valid_until,
                 allowed_contexts=["case_studies"], prohibited_contexts=[])


def block(content="We cut onboarding time 40%.", claim_ids=("c1",)):
    return GeneratedBlock(block_id="b1", kind="text", content=content,
                          claim_ids=list(claim_ids), source_record_ids=["s1"],
                          editable=True)


def evidence(claim_id="c1"):
    return [EvidenceLink(claim_id=claim_id, source_record_id="s1",
                         locator="p.3", excerpt="onboarding time fell 40%")]


def test_approved_claim_with_evidence_has_no_flags():
    assert validate_block(block(), {"c1": claim()}, {"c1": evidence()}, NOW) == []


def test_unknown_claim_is_missing_source():
    assert validate_block(block(), {}, {}, NOW) == ["MISSING_SOURCE"]


def test_unapproved_claim_flagged():
    flags = validate_block(block(), {"c1": claim("pending_approval")}, {"c1": evidence()}, NOW)
    assert "UNAPPROVED_CLAIM" in flags


def test_expired_claim_flagged():
    flags = validate_block(block(), {"c1": claim(valid_until="2026-07-01")},
                           {"c1": evidence()}, NOW)
    assert "EXPIRED_CLAIM" in flags


def test_claim_without_evidence_is_missing_source():
    flags = validate_block(block(), {"c1": claim()}, {}, NOW)
    assert "MISSING_SOURCE" in flags


def test_bare_assertion_without_claim_is_unapproved():
    flags = validate_block(block("We reduced churn by 22%.", claim_ids=()), {}, {}, NOW)
    assert flags == ["UNAPPROVED_CLAIM"]


def test_neutral_prose_without_claim_is_clean():
    flags = validate_block(block("This section describes the engagement.", claim_ids=()),
                           {}, {}, NOW)
    assert flags == []


def test_flags_are_deduplicated_across_two_bad_claims():
    bad = {"c1": claim("rejected", id_="c1"), "c2": claim("rejected", id_="c2")}
    flags = validate_block(block(claim_ids=("c1", "c2")), bad, {}, NOW)
    assert len(flags) == len(set(flags))
    assert set(flags) == {"UNAPPROVED_CLAIM", "MISSING_SOURCE"}


def test_assertion_detector_catches_prd_shapes():
    for text in ["improved 12%", "a 3x return", "we reduced cost",
                 "the fastest option", "saved $40,000", "#1 in retention",
                 "ranked #1 nationally"]:
        assert contains_verifiable_assertion(text), text
    for text in ["We will run four workshops.", "Scope covers two milestones."]:
        assert not contains_verifiable_assertion(text), text


def test_expired_and_rejected_claims_cannot_enter_a_new_version():
    assert usable_in_new_version(claim(), NOW) is True
    assert usable_in_new_version(claim("rejected"), NOW) is False
    assert usable_in_new_version(claim("expired"), NOW) is False
    assert usable_in_new_version(claim(valid_until="2026-07-01"), NOW) is False


def test_claim_whose_window_has_not_opened_yet_is_unusable():
    assert usable_in_new_version(claim(valid_from="2026-09-01"), NOW) is False
    assert usable_in_new_version(claim(valid_from="2026-01-01"), NOW) is True


def test_claim_valid_exactly_today_is_usable():
    assert usable_in_new_version(claim(valid_until=NOW), NOW) is True
    assert usable_in_new_version(claim(valid_from=NOW), NOW) is True

