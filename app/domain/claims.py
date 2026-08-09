"""Claim and evidence enforcement (I1, I7).

I1: a client-facing claim is either a template literal or references an approved
claim backed by evidence. The assertion detector is what makes that enforceable —
prose that asserts something checkable ("we reduced churn 22%") and cites no claim
is flagged rather than shipped.

The detector is deliberately conservative in one direction only: a false positive
costs a reviewer one dismissal, a false negative puts an unbacked number in front
of a client. When in doubt it flags.
"""

import re

from app.domain.schemas import Claim, EvidenceLink, GeneratedBlock

ASSERTION_PATTERNS = (
    re.compile(r"\b\d+(\.\d+)?\s?%"),
    re.compile(r"\b\d[\d,]*(\.\d+)?x\b", re.IGNORECASE),
    re.compile(r"\b(increased|decreased|reduced|grew|saved|delivered|achieved)\b", re.IGNORECASE),
    # "#1" needs its own alternative: \b before "#" cannot match at a word start.
    re.compile(r"\b(best|fastest|leading|award-winning|industry-leading)\b|#1", re.IGNORECASE),
    re.compile(r"\$\s?\d"),
)


def contains_verifiable_assertion(text: str) -> bool:
    return any(pattern.search(text) for pattern in ASSERTION_PATTERNS)


def validate_block(
    block: GeneratedBlock,
    claims_by_id: dict[str, Claim],
    evidence_by_claim: dict[str, list[EvidenceLink]],
    now: str,
) -> list[str]:
    """Return the flag codes this block earns, deduplicated and ordered."""
    flags: list[str] = []

    def flag(code: str) -> None:
        if code not in flags:
            flags.append(code)

    for claim_id in block.claim_ids:
        claim = claims_by_id.get(claim_id)
        if claim is None:
            flag("MISSING_SOURCE")
            continue
        if claim.status != "approved":
            flag("UNAPPROVED_CLAIM")
        if claim.valid_until and claim.valid_until < now:
            flag("EXPIRED_CLAIM")
        if not evidence_by_claim.get(claim_id):
            flag("MISSING_SOURCE")

    if contains_verifiable_assertion(block.content) and not block.claim_ids:
        flag("UNAPPROVED_CLAIM")

    return flags


def usable_in_new_version(claim: Claim, now: str) -> bool:
    """I7 — expired or rejected claims cannot be used in a new version.

    Bounds are inclusive: a claim valid *until* today is still valid today.
    """
    if claim.status != "approved":
        return False
    window_open = not claim.valid_from or claim.valid_from <= now
    not_expired = not claim.valid_until or claim.valid_until >= now
    return window_open and not_expired
