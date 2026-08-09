"""Generation adapters.

The live-model tests never touch the network: they replace ``_client`` and assert
on the kwargs the SDK would receive. That is the only way to pin a request shape
whose wrong values fail with a 400 in production rather than an exception here.
"""

import pytest

from app.adapters.generation import (
    DEFAULT_MODEL,
    MAX_TOKENS,
    BlockOutput,
    ClaudeGenerationAdapter,
    FixtureGenerationAdapter,
    SectionOutput,
    _respond,
    get_generation_adapter,
    load_section_fixture,
    source_snapshot_hash,
)
from app.domain.claims import contains_verifiable_assertion
from app.domain.schemas import SECTION_KEYS

NOW = "2026-08-01T10:00:00Z"


def generate(request):
    return FixtureGenerationAdapter().generate(request, now=NOW)


# --- adapter selection ------------------------------------------------------


def test_fixture_mode_is_the_default(monkeypatch):
    monkeypatch.delenv("GENERATION_MODE", raising=False)
    assert isinstance(get_generation_adapter(), FixtureGenerationAdapter)


def test_unrecognised_mode_falls_back_to_fixtures(monkeypatch):
    """A typo must not silently start spending on the live API."""
    monkeypatch.setenv("GENERATION_MODE", "clade")
    assert isinstance(get_generation_adapter(), FixtureGenerationAdapter)


def test_claude_mode_is_opt_in(monkeypatch):
    monkeypatch.setenv("GENERATION_MODE", "CLAUDE")
    assert isinstance(get_generation_adapter(), ClaudeGenerationAdapter)


# --- fixture generation ----------------------------------------------------


def test_every_section_key_has_a_fixture():
    for key in SECTION_KEYS:
        assert load_section_fixture(key).key == key


def test_only_requested_sections_are_returned_in_request_order(draft_request):
    request = draft_request.model_copy(
        update={"requested_sections": ["pricing", "scope"]})
    assert [s.key for s in generate(request).sections] == ["pricing", "scope"]


def test_fixture_generation_is_deterministic(draft_request):
    first, second = generate(draft_request), generate(draft_request)
    assert first == second


def test_generation_run_id_follows_the_snapshot_hash(draft_request):
    response = generate(draft_request)
    assert response.source_snapshot_hash
    assert response.generation_run_id == f"run-{response.source_snapshot_hash[:16]}"


def test_snapshot_hash_moves_when_a_source_changes(draft_request):
    edited = draft_request.model_copy(update={"template_id": "tmpl-other"})
    assert source_snapshot_hash(edited) != source_snapshot_hash(draft_request)


def test_snapshot_hash_moves_when_claim_content_changes(draft_request):
    first, *rest = draft_request.approved_claims
    edited = draft_request.model_copy(update={
        "approved_claims": [first.model_copy(update={"text": "Revised claim"}), *rest]
    })
    assert source_snapshot_hash(edited) != source_snapshot_hash(draft_request)


def test_snapshot_hash_moves_when_claim_evidence_changes(draft_request):
    first, *rest = draft_request.approved_claims
    evidence = first.evidence[0].model_copy(update={"excerpt": "Revised evidence"})
    edited = draft_request.model_copy(update={
        "approved_claims": [first.model_copy(update={"evidence": [evidence]}), *rest]
    })
    assert source_snapshot_hash(edited) != source_snapshot_hash(draft_request)


def test_block_ids_are_assigned_by_us_not_by_the_model(draft_request):
    request = draft_request.model_copy(update={"requested_sections": ["understanding"]})
    ids = [b.block_id for b in generate(request).sections[0].blocks]
    assert ids == [f"understanding-{i}" for i in range(1, len(ids) + 1)]


# --- I1: assertions need claims -------------------------------------------


def test_every_surviving_block_with_an_assertion_carries_claim_ids(draft_request):
    for section in generate(draft_request).sections:
        for block in section.blocks:
            if contains_verifiable_assertion(block.content):
                assert block.claim_ids, f"{block.block_id} asserts with no claim"


def test_claims_used_maps_every_referenced_claim(draft_request):
    response = generate(draft_request)
    referenced = {c for s in response.sections for b in s.blocks for c in b.claim_ids}
    assert referenced == {u.claim_id for u in response.claims_used}
    assert referenced, "the fixtures should exercise at least one claim"


def test_claim_usage_names_the_block_that_used_it(draft_request):
    response = generate(draft_request)
    block_ids = {b.block_id for s in response.sections for b in s.blocks}
    for usage in response.claims_used:
        assert usage.block_id in block_ids
        assert usage.validation == "approved"


def test_pending_claim_is_dropped_and_flagged(draft_request_with_pending_claim):
    response = generate(draft_request_with_pending_claim)
    assert any(f.code == "UNAPPROVED_CLAIM" for f in response.unresolved_flags)
    assert response.claims_used == []
    for section in response.sections:
        for block in section.blocks:
            assert not contains_verifiable_assertion(block.content)


def test_expired_claim_is_dropped_and_flagged(draft_request_with_expired_claim):
    """I7 — approved once is not approved forever."""
    response = generate(draft_request_with_expired_claim)
    assert any(f.code == "UNAPPROVED_CLAIM" for f in response.unresolved_flags)
    assert response.claims_used == []


def test_approved_claim_without_evidence_is_dropped_and_flagged(draft_request):
    claim = draft_request.approved_claims[0]
    request = draft_request.model_copy(update={
        "approved_claims": [claim.model_copy(update={"evidence": []})]
    })
    rogue = SectionOutput(key="case_studies", blocks=[BlockOutput(
        content=claim.text,
        claim_ids=[claim.id],
        source_record_ids=["src-case-northwind"],
    )])
    response = _respond(request, [rogue], NOW)
    assert response.sections[0].blocks == []
    assert [flag.code for flag in response.unresolved_flags] == ["UNAPPROVED_CLAIM"]


def test_dropped_block_flags_name_the_block(draft_request_with_pending_claim):
    flags = generate(draft_request_with_pending_claim).unresolved_flags
    assert all(f.related_ids for f in flags)
    assert all(f.severity == "blocking" for f in flags)


def test_an_uncited_assertion_is_discarded_whatever_produced_it(draft_request):
    """The rule is enforced on output, not requested in the prompt."""
    rogue = SectionOutput(key="scope", blocks=[
        BlockOutput(content="We reduced onboarding effort by 90%.",
                    source_record_ids=["src-notes-manual"]),
        BlockOutput(content="The workshop series runs over four weeks.",
                    source_record_ids=["src-notes-manual"]),
    ])
    response = _respond(draft_request, [rogue], NOW)
    assert [b.content for b in response.sections[0].blocks] == [
        "The workshop series runs over four weeks."]
    assert [f.code for f in response.unresolved_flags] == ["UNAPPROVED_CLAIM"]


def test_a_block_citing_an_unknown_claim_is_discarded(draft_request):
    rogue = SectionOutput(key="scope", blocks=[
        BlockOutput(content="We reduced onboarding effort by 90%.",
                    claim_ids=["claim-invented"],
                    source_record_ids=["src-notes-manual"])])
    response = _respond(draft_request, [rogue], NOW)
    assert response.sections[0].blocks == []
    assert "claim-invented" in response.unresolved_flags[0].message


def test_a_block_with_no_source_record_is_discarded(draft_request):
    rogue = SectionOutput(key="scope", blocks=[
        BlockOutput(content="The workshop series runs over four weeks.")])
    response = _respond(draft_request, [rogue], NOW)
    assert response.sections[0].blocks == []
    assert [f.code for f in response.unresolved_flags] == ["MISSING_SOURCE"]


# --- pricing prose must not restate figures -------------------------------


@pytest.mark.parametrize("key", ["pricing", "payment_schedule"])
def test_money_sections_state_no_figures(key):
    """Prose that repeats a figure will disagree with the calculated quote."""
    for block in load_section_fixture(key).blocks:
        assert not any(ch.isdigit() for ch in block.content), block.content


# --- live adapter request shape -------------------------------------------


class _FakeResponse:
    stop_reason = "end_turn"

    def __init__(self, key="scope"):
        self.parsed_output = SectionOutput(key=key, blocks=[
            BlockOutput(content="Neutral prose about the workshop series.",
                        source_record_ids=["src-notes-manual"])])


class _Refusal:
    stop_reason = "refusal"
    parsed_output = None


def _fake_client(monkeypatch, response_factory):
    calls: list[dict] = []

    class FakeMessages:
        def parse(self, **kwargs):
            calls.append(kwargs)
            return response_factory()

    monkeypatch.setattr(
        "app.adapters.generation._client",
        lambda: type("C", (), {"messages": FakeMessages()})(),
    )
    return calls


def test_claude_adapter_request_shape(monkeypatch, draft_request):
    calls = _fake_client(monkeypatch, _FakeResponse)
    request = draft_request.model_copy(update={"requested_sections": ["scope"]})
    ClaudeGenerationAdapter().generate(request, now=NOW)

    sent = calls[0]
    assert sent["model"] == DEFAULT_MODEL
    assert sent["thinking"] == {"type": "adaptive"}
    assert "budget_tokens" not in str(sent["thinking"])
    assert sent["max_tokens"] == MAX_TOKENS
    for banned in ("temperature", "top_p", "top_k"):
        assert banned not in sent
    assert sent["messages"][-1]["role"] == "user"
    assert sent["output_format"] is SectionOutput
    assert "scope" in sent["messages"][0]["content"]


def test_claude_adapter_calls_once_per_requested_section(monkeypatch, draft_request):
    calls = _fake_client(monkeypatch, _FakeResponse)
    request = draft_request.model_copy(
        update={"requested_sections": ["scope", "understanding"]})
    ClaudeGenerationAdapter().generate(request, now=NOW)
    assert len(calls) == 2


def test_model_name_is_read_from_the_environment(monkeypatch, draft_request):
    calls = _fake_client(monkeypatch, _FakeResponse)
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5")
    request = draft_request.model_copy(update={"requested_sections": ["scope"]})
    ClaudeGenerationAdapter().generate(request, now=NOW)
    assert calls[0]["model"] == "claude-opus-5"


def test_a_refusal_costs_one_section_not_the_draft(monkeypatch, draft_request):
    _fake_client(monkeypatch, _Refusal)
    request = draft_request.model_copy(update={"requested_sections": ["scope"]})
    response = ClaudeGenerationAdapter().generate(request, now=NOW)
    assert response.sections == []
    assert [f.code for f in response.unresolved_flags] == ["SCHEMA_ERROR"]


def test_the_section_key_comes_from_the_request_not_the_model(monkeypatch, draft_request):
    """A model returning the wrong key must not reorder or mislabel the draft."""
    _fake_client(monkeypatch, lambda: _FakeResponse(key="case_studies"))
    request = draft_request.model_copy(update={"requested_sections": ["scope"]})
    assert [s.key for s in
            ClaudeGenerationAdapter().generate(request, now=NOW).sections] == ["scope"]
