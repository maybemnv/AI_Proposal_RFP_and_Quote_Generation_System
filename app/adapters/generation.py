"""Section-scoped draft generation.

Two adapters, one contract. ``FixtureGenerationAdapter`` reads deterministic
copy from disk — no key, no network, identical output every run, which is what a
demo needs. ``ClaudeGenerationAdapter`` calls the live model. Both then run the
*same* post-processing, and that is the point: I1 is enforced after generation,
not requested during it. A block that asserts a measurable outcome without a
usable approved claim is discarded and flagged, whether a fixture or a model
produced it.

One call per requested section, so each call is bounded and independently
retryable, and a refusal costs one section rather than the whole draft.
"""

import json
import os
from pathlib import Path
from typing import Any, Protocol

from pydantic import Field

from app.domain.claims import contains_verifiable_assertion, usable_in_new_version
from app.domain.pricing import compute_input_hash
from app.domain.prompts import SYSTEM_PROMPT, prompt_for
from app.domain.schemas import (
    CamelModel,
    ClaimUsage,
    GeneratedBlock,
    GenerateDraftRequest,
    GenerateDraftResponse,
    GeneratedSection,
    ValidationFlag,
)

DEFAULT_MODEL = "claude-opus-5"
MAX_TOKENS = 16000
FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "generation"


def model_name() -> str:
    """Read at call time. A module-level env read binds whatever was set at import."""
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


class BlockOutput(CamelModel):
    """What the model is asked to return. Deliberately narrower than
    ``GeneratedBlock``: block ids and the editable flag are ours to assign, not
    the model's to choose. Inherits the contract's camelCase aliases and
    ``extra="forbid"``, so a stray field fails loudly instead of vanishing."""

    kind: str = "text"
    content: str
    claim_ids: list[str] = Field(default_factory=list)
    source_record_ids: list[str] = Field(default_factory=list)


class SectionOutput(CamelModel):
    key: str
    blocks: list[BlockOutput]


class GenerationAdapter(Protocol):
    def generate(
        self, request: GenerateDraftRequest, *, now: str
    ) -> GenerateDraftResponse: ...


def source_snapshot_hash(request: GenerateDraftRequest) -> str:
    """Hash of everything a draft was derived from, so a later reader can tell
    whether the sources have moved under a generated section."""
    return compute_input_hash({
        "opportunity": (
            request.opportunity.model_dump(by_alias=True) if request.opportunity else None
        ),
        "discovery": [d.model_dump(by_alias=True) for d in request.discovery],
        "requirements": [r.model_dump(by_alias=True) for r in request.requirements],
        "scope": request.scope.model_dump(by_alias=True) if request.scope else None,
        "claims": sorted(c.id for c in request.approved_claims),
        "templateId": request.template_id,
    })


def _usable_claim_ids(request: GenerateDraftRequest, now: str) -> set[str]:
    """I7 at the generation boundary: a claim outside its validity window, or not
    approved, cannot enter a new version even if it was passed in."""
    return {c.id for c in request.approved_claims if usable_in_new_version(c, now)}


def _enforce(
    sections: list[SectionOutput],
    request: GenerateDraftRequest,
    now: str,
) -> tuple[list[GeneratedSection], list[ClaimUsage], list[ValidationFlag]]:
    """Turn model or fixture output into contract types, dropping what I1 forbids.

    A block survives only if every claim it cites is usable, and only if it cites
    at least one claim when it asserts something measurable. Everything dropped
    leaves a blocking flag naming the block, so the UI can show what was removed
    rather than silently shipping a shorter draft.
    """
    usable = _usable_claim_ids(request, now)
    kept: list[GeneratedSection] = []
    used: list[ClaimUsage] = []
    flags: list[ValidationFlag] = []

    for section in sections:
        blocks: list[GeneratedBlock] = []
        for index, raw in enumerate(section.blocks, start=1):
            block_id = f"{section.key}-{index}"
            unusable = [c for c in raw.claim_ids if c not in usable]
            if unusable:
                flags.append(ValidationFlag(
                    code="UNAPPROVED_CLAIM", severity="blocking",
                    message=(f"{section.key}/{block_id} cites claims that are not "
                             f"approved and current: {', '.join(sorted(unusable))}"),
                    related_ids=[block_id, *sorted(unusable)],
                ))
                continue
            if contains_verifiable_assertion(raw.content) and not raw.claim_ids:
                flags.append(ValidationFlag(
                    code="UNAPPROVED_CLAIM", severity="blocking",
                    message=(f"{section.key}/{block_id} asserts a measurable outcome "
                             "with no approved claim behind it"),
                    related_ids=[block_id],
                ))
                continue
            if not raw.source_record_ids:
                flags.append(ValidationFlag(
                    code="MISSING_SOURCE", severity="blocking",
                    message=f"{section.key}/{block_id} cites no source record",
                    related_ids=[block_id],
                ))
                continue

            block = GeneratedBlock(
                block_id=block_id,
                kind=raw.kind,
                content=raw.content,
                claim_ids=list(raw.claim_ids),
                source_record_ids=list(raw.source_record_ids),
            )
            blocks.append(block)
            used.extend(
                ClaimUsage(claim_id=claim_id, block_id=block_id, validation="approved")
                for claim_id in raw.claim_ids
            )
        kept.append(GeneratedSection(key=section.key, blocks=blocks))

    return kept, used, flags


def _respond(
    request: GenerateDraftRequest,
    sections: list[SectionOutput],
    now: str,
    extra_flags: list[ValidationFlag] | None = None,
) -> GenerateDraftResponse:
    kept, used, flags = _enforce(sections, request, now)
    snapshot = source_snapshot_hash(request)
    return GenerateDraftResponse(
        proposal_version_id=request.proposal_version_id,
        sections=kept,
        claims_used=used,
        unresolved_flags=[*(extra_flags or []), *flags],
        generation_run_id=f"run-{snapshot[:16]}",
        source_snapshot_hash=snapshot,
    )


def load_section_fixture(section_key: str) -> SectionOutput:
    """Read a stored section into the model-output shape.

    Fixture files carry a ``blockId`` for readability, but block ids are assigned
    during enforcement, not taken from input — dropping it here keeps fixtures and
    live model output on exactly one code path.
    """
    path = FIXTURE_ROOT / f"{section_key}.json"
    if not path.exists():
        raise FileNotFoundError(f"missing generation fixture: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SectionOutput.model_validate({
        "key": raw["key"],
        "blocks": [{k: v for k, v in block.items() if k != "blockId"}
                   for block in raw["blocks"]],
    })


class FixtureGenerationAdapter:
    """Deterministic drafts from disk. No key, no network, byte-identical reruns."""

    def generate(
        self, request: GenerateDraftRequest, *, now: str
    ) -> GenerateDraftResponse:
        sections = [load_section_fixture(key) for key in request.requested_sections]
        return _respond(request, sections, now)


def _client() -> Any:
    """Imported lazily so the module loads, and fixture mode runs, without the SDK
    configured or a key present."""
    from anthropic import Anthropic

    return Anthropic()


class ClaudeGenerationAdapter:
    """Live generation. One call per section.

    The call shape is fixed by what this model accepts: adaptive thinking with no
    token budget, no sampling parameters, no assistant prefill. Sending any of
    them is a 400, so none of them appear here.
    """

    def generate(
        self, request: GenerateDraftRequest, *, now: str
    ) -> GenerateDraftResponse:
        client = _client()
        sections: list[SectionOutput] = []
        refusals: list[ValidationFlag] = []

        for section_key in request.requested_sections:
            response = client.messages.parse(
                model=model_name(),
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_format=SectionOutput,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user",
                           "content": prompt_for(section_key, request)}],
            )
            if getattr(response, "stop_reason", None) == "refusal":
                refusals.append(ValidationFlag(
                    code="SCHEMA_ERROR", severity="blocking",
                    message=f"the model declined to draft section {section_key}",
                    related_ids=[section_key],
                ))
                continue
            parsed = response.parsed_output
            if parsed is None:
                refusals.append(ValidationFlag(
                    code="SCHEMA_ERROR", severity="blocking",
                    message=f"section {section_key} did not parse into the contract",
                    related_ids=[section_key],
                ))
                continue
            sections.append(SectionOutput.model_validate(
                {**parsed.model_dump(), "key": section_key}))

        return _respond(request, sections, now, extra_flags=refusals)


def get_generation_adapter() -> GenerationAdapter:
    """``GENERATION_MODE=claude`` opts into the live model. Anything else, including
    an unset variable, is fixture mode — a demo cannot fail because a key is
    missing."""
    if os.environ.get("GENERATION_MODE", "fixture").strip().lower() == "claude":
        return ClaudeGenerationAdapter()
    return FixtureGenerationAdapter()
