"""Validation service — the single chokepoint for I8.

Nothing reaches a client without passing through here. `/validate`, `/submit`,
and `/deliver` all call `validate_version`, so there is exactly one definition of
"ready", and adding a ninth blocking condition means editing one function rather
than three endpoints.

Two properties the callers depend on:

*Total, not fail-fast.* Every check runs and every flag is returned. A reviewer
fixing one blocker should not discover a second one on the next submit, and a
third after that.

*Deterministic order.* Flags come back in a fixed sequence — claims, price,
requirements, approvals, document — so a UI listing them does not reshuffle
between two identical requests.
"""

from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from app.domain.claims import validate_block
from app.domain.pricing import PricingError, calculate_quote
from app.domain.schemas import (
    Approval,
    Claim,
    EvidenceLink,
    GeneratedSection,
    PricingRule,
    ProposalVersion,
    Requirement,
    ValidationFlag,
)

# What each block-level code from validate_block means to a reader. The codes
# themselves come from app.domain.claims, which decides *when* they apply; this
# module only decides how to phrase them and what they point at.
_BLOCK_MESSAGES = {
    "MISSING_SOURCE": "cites a claim that is unknown or has no evidence behind it",
    "UNAPPROVED_CLAIM": "asserts something measurable without an approved claim",
    "EXPIRED_CLAIM": "cites a claim whose validity window has closed",
}


def _flag(code: str, message: str, related_ids: list[str],
          severity: str = "blocking") -> ValidationFlag:
    return ValidationFlag(code=code, severity=severity, message=message,
                          related_ids=related_ids)


def _coerce_sections(
    sections: list[Any],
) -> tuple[list[GeneratedSection], list[ValidationFlag]]:
    """Accept already-parsed sections or raw payloads.

    A section arriving from a provider or a stored draft may not satisfy the
    contract. That is a SCHEMA_ERROR to report, not an exception to raise —
    validation's job is to describe what is wrong, not to fail on it.
    """
    parsed: list[GeneratedSection] = []
    flags: list[ValidationFlag] = []
    for index, section in enumerate(sections):
        if isinstance(section, GeneratedSection):
            parsed.append(section)
            continue
        try:
            parsed.append(GeneratedSection.model_validate(section))
        except ValidationError as exc:
            key = section.get("key", f"section-{index}") if isinstance(section, dict) \
                else f"section-{index}"
            flags.append(_flag(
                "SCHEMA_ERROR",
                f"section {key} does not satisfy the contract: {exc.error_count()} "
                "field error(s)",
                [str(key)],
            ))
    return parsed, flags


def _claim_flags(
    sections: list[GeneratedSection],
    claims_by_id: dict[str, Claim],
    evidence_by_claim: dict[str, list[EvidenceLink]],
    now: str,
) -> list[ValidationFlag]:
    """I1 and I7 at the version level, block by block."""
    flags: list[ValidationFlag] = []
    for section in sections:
        for block in section.blocks:
            for code in validate_block(block, claims_by_id, evidence_by_claim, now):
                flags.append(_flag(
                    code,
                    f"{section.key}/{block.block_id} {_BLOCK_MESSAGES[code]}",
                    [block.block_id, *block.claim_ids],
                ))
    return flags


def _price_flags(
    version: ProposalVersion, rules: dict[str, PricingRule],
) -> list[ValidationFlag]:
    """I2 and I3 — recompute the quote and compare.

    Comparing the hash as well as the total is what makes this worth doing: a
    total can be made to agree by editing two lines in opposite directions, but
    the hash covers every input that produced it.
    """
    quote = version.quote
    line_ids = [line.id for line in quote.lines]
    mismatch = _flag(
        "PRICE_MISMATCH",
        "stored quote does not match a recomputation from its rule versions",
        line_ids or [version.id],
    )
    try:
        recomputed = calculate_quote(
            # quantity is a float on the wire and Decimal in the engine (I9).
            # Via str, never Decimal(float) — the engine hashes
            # str(Decimal(str(quantity))), so this round-trips byte for byte.
            [{"id": line.id, "label": line.label, "ruleId": line.rule_id,
              "quantity": Decimal(str(line.quantity)), "optional": line.optional,
              "selected": line.selected, "sourceRecordIds": line.source_record_ids}
             for line in quote.lines],
            rules,
            quote.currency,
            discount_minor=quote.discount_minor,
            tax_minor=quote.tax_minor,
            installments=[i.model_dump(by_alias=True) for i in quote.payment_schedule],
            calculated_at=quote.calculated_at,
        )
    except PricingError:
        # A rule deleted or edited since the quote was calculated. The quote is
        # no longer reproducible, which is exactly what PRICE_MISMATCH means.
        return [mismatch]

    if (recomputed.total_minor != quote.total_minor
            or recomputed.input_hash != quote.input_hash):
        return [mismatch]
    return []


def _requirement_flags(
    version: ProposalVersion, requirements: list[Requirement],
) -> list[ValidationFlag]:
    flags: list[ValidationFlag] = []
    for requirement in requirements:
        if requirement.status == "open_question":
            flags.append(_flag(
                "UNRESOLVED_REQUIREMENT",
                f"requirement {requirement.id} is still an open question",
                [requirement.id],
            ))
        elif requirement.status == "assumption":
            flags.append(_flag(
                "UNRESOLVED_REQUIREMENT",
                f"requirement {requirement.id} is an assumption and needs "
                "customer confirmation",
                [requirement.id], severity="warning",
            ))
        if requirement.confidence == "low":
            flags.append(_flag(
                "UNRESOLVED_REQUIREMENT",
                f"requirement {requirement.id} was extracted with low confidence",
                [requirement.id], severity="warning",
            ))

    for index, question in enumerate(version.scope.open_questions, start=1):
        flags.append(_flag(
            "UNRESOLVED_REQUIREMENT",
            f"scope carries an unanswered question: {question}",
            [f"{version.id}-open-question-{index}"],
        ))
    return flags


def _approval_flags(approvals: list[Approval]) -> list[ValidationFlag]:
    """I6 — every required approval, not merely one of them."""
    return [
        _flag(
            "MISSING_APPROVAL",
            f"{approval.kind} approval by {approval.required_role} is "
            f"{approval.decision}",
            [approval.id],
        )
        for approval in approvals
        if approval.decision != "approved"
    ]


def validate_version(
    *,
    version: ProposalVersion,
    sections: list[Any],
    claims_by_id: dict[str, Claim],
    evidence_by_claim: dict[str, list[EvidenceLink]],
    rules: dict[str, PricingRule],
    requirements: list[Requirement],
    approvals: list[Approval],
    document_status: str,
    now: str,
) -> list[ValidationFlag]:
    """Every blocking and warning condition on one version, in a fixed order."""
    parsed, flags = _coerce_sections(sections)
    flags += _claim_flags(parsed, claims_by_id, evidence_by_claim, now)
    flags += _price_flags(version, rules)
    flags += _requirement_flags(version, requirements)
    flags += _approval_flags(approvals)

    if document_status == "failed":
        flags.append(_flag(
            "RENDER_ERROR",
            "the document failed to render",
            [version.id],
        ))
    return flags


def blocking_flags(flags: list[ValidationFlag]) -> list[ValidationFlag]:
    """What stops delivery. Warnings inform a reviewer; these stop the workflow."""
    return [flag for flag in flags if flag.severity == "blocking"]
