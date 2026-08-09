"""Validation service.

Every bundle here is built from real models and the real pricing engine, so a
PRICE_MISMATCH in these tests means the recomputation genuinely disagrees — not
that a hand-written dict drifted from the contract.
"""

from app.domain.validation import blocking_flags, validate_version


def codes(flags):
    return {f.code for f in flags}


def test_clean_version_has_no_blocking_flags(clean_bundle):
    flags = validate_version(**clean_bundle)
    assert blocking_flags(flags) == []


def test_price_mismatch_detected_when_total_is_tampered(clean_bundle):
    bundle = dict(clean_bundle)
    v = bundle["version"]
    bundle["version"] = v.model_copy(update={
        "quote": v.quote.model_copy(update={"total_minor": v.quote.total_minor + 1})})
    assert "PRICE_MISMATCH" in codes(validate_version(**bundle))


def test_price_mismatch_detected_when_only_the_hash_is_tampered(clean_bundle):
    """A total can be made to agree by editing two numbers; the hash cannot."""
    bundle = dict(clean_bundle)
    v = bundle["version"]
    bundle["version"] = v.model_copy(update={
        "quote": v.quote.model_copy(update={"input_hash": "0" * 64})})
    assert "PRICE_MISMATCH" in codes(validate_version(**bundle))


def test_open_question_produces_unresolved_requirement(bundle_with_open_question):
    assert "UNRESOLVED_REQUIREMENT" in codes(validate_version(**bundle_with_open_question))


def test_scope_open_question_produces_unresolved_requirement(clean_bundle):
    bundle = dict(clean_bundle)
    v = bundle["version"]
    bundle["version"] = v.model_copy(update={
        "scope": v.scope.model_copy(update={
            "open_questions": ["Who signs off on the data migration?"]})})
    assert "UNRESOLVED_REQUIREMENT" in codes(validate_version(**bundle))


def test_pending_approval_produces_missing_approval(bundle_with_pending_approval):
    assert "MISSING_APPROVAL" in codes(validate_version(**bundle_with_pending_approval))


def test_rejected_approval_also_produces_missing_approval(clean_bundle,
                                                          rejected_approval):
    bundle = dict(clean_bundle) | {"approvals": rejected_approval}
    assert "MISSING_APPROVAL" in codes(validate_version(**bundle))


def test_failed_document_produces_render_error(clean_bundle):
    bundle = dict(clean_bundle) | {"document_status": "failed"}
    assert "RENDER_ERROR" in codes(validate_version(**bundle))


def test_document_still_rendering_is_not_a_render_error(clean_bundle):
    bundle = dict(clean_bundle) | {"document_status": "rendering"}
    assert "RENDER_ERROR" not in codes(validate_version(**bundle))


def test_expired_claim_produces_expired_claim(bundle_with_expired_claim):
    assert "EXPIRED_CLAIM" in codes(validate_version(**bundle_with_expired_claim))


def test_claim_without_evidence_produces_missing_source(clean_bundle):
    bundle = dict(clean_bundle) | {"evidence_by_claim": {}}
    assert "MISSING_SOURCE" in codes(validate_version(**bundle))


def test_unknown_claim_produces_missing_source(clean_bundle):
    bundle = dict(clean_bundle) | {"claims_by_id": {}}
    assert "MISSING_SOURCE" in codes(validate_version(**bundle))


def test_uncited_assertion_produces_unapproved_claim(clean_bundle, rogue_sections):
    bundle = dict(clean_bundle) | {"sections": rogue_sections}
    assert "UNAPPROVED_CLAIM" in codes(validate_version(**bundle))


def test_assumption_requirement_is_a_warning_not_a_blocker(bundle_with_assumption):
    flags = validate_version(**bundle_with_assumption)
    assert blocking_flags(flags) == []
    assert any(f.severity == "warning" for f in flags)


def test_low_confidence_requirement_is_a_warning_not_a_blocker(clean_bundle,
                                                               low_confidence_requirements):
    bundle = dict(clean_bundle) | {"requirements": low_confidence_requirements}
    flags = validate_version(**bundle)
    assert blocking_flags(flags) == []
    assert any(f.severity == "warning" for f in flags)


def test_every_flag_carries_related_ids(clean_bundle, bundle_with_open_question):
    for bundle in (clean_bundle, bundle_with_open_question):
        for flag in validate_version(**bundle):
            assert flag.related_ids


def test_blocking_flags_filters_out_warnings(bundle_with_assumption):
    flags = validate_version(**bundle_with_assumption)
    assert flags, "the assumption should have produced at least a warning"
    assert blocking_flags(flags) == []


def test_flag_codes_are_stable_across_repeat_runs(clean_bundle, rogue_sections):
    """The endpoints show these to a reviewer; the order must not shuffle."""
    bundle = dict(clean_bundle) | {"sections": rogue_sections}
    first = [(f.code, f.message) for f in validate_version(**bundle)]
    second = [(f.code, f.message) for f in validate_version(**bundle)]
    assert first == second


def test_a_missing_pricing_rule_is_a_price_mismatch_not_a_crash(clean_bundle):
    """A rule deleted after the quote was calculated must flag, never raise."""
    bundle = dict(clean_bundle) | {"rules": {}}
    assert "PRICE_MISMATCH" in codes(validate_version(**bundle))


def test_schema_error_when_a_section_is_not_a_section(clean_bundle):
    bundle = dict(clean_bundle) | {"sections": [{"key": "scope", "blocks": "not-a-list"}]}
    assert "SCHEMA_ERROR" in codes(validate_version(**bundle))
