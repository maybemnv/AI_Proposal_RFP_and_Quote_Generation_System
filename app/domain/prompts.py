"""Prompts for section generation.

The system prompt carries the rules that make I1 achievable: the model may only
assert what an approved claim supports, must cite the claim on any block that
asserts, and must not restate pricing figures — the pricing section renders from
the calculated ``Quote``, never from prose. The rules are stated here *and*
enforced after the fact in ``app.adapters.generation``, because a prompt is a
request and an invariant needs a check.

Context is passed as JSON rather than prose so the model sees the same field
names the contract uses, and so a schema change shows up in the prompt.
"""

import json
from typing import Any

from app.domain.schemas import SECTION_KEYS, GenerateDraftRequest

SYSTEM_PROMPT = """You draft sections of a commercial proposal for a consulting firm.

Rules, in priority order:

1. Never invent a number, a metric, a client name, or an outcome. Every factual
   statement must be supported by the supplied context.
2. If a block asserts a measurable outcome — a percentage, a multiple, a money
   figure, or a verb like "reduced", "increased", "saved", "delivered",
   "achieved", or a superlative like "leading" or "fastest" — it MUST be
   supported by one of the supplied approved claims, and you MUST list that
   claim's id in that block's claimIds. A block asserting an outcome with no
   claim id will be discarded.
3. If no approved claim supports a point you want to make, write the neutral
   version of it instead, with an empty claimIds. Neutral prose is always
   acceptable; an uncited assertion never is.
4. Never state prices, rates, totals, discounts, tax, or payment percentages.
   The pricing and payment tables are rendered from calculated figures. Prose
   that restates a figure will disagree with the calculation sooner or later.
5. Every block must list the sourceRecordIds it was drawn from.
6. Write for a client executive: concrete, plain, and short. Two to four
   sentences per block. No marketing register.

Return only the requested section."""

_SECTION_BRIEFS: dict[str, str] = {
    "executive_summary": (
        "The ask, the approach, and the outcome the client can expect. This is the "
        "one section where claim-backed outcomes belong, if any claim supports them."
    ),
    "understanding": (
        "Restate the client's situation in their own terms, from the discovery "
        "inputs. Demonstrate comprehension; assert nothing new."
    ),
    "scope": (
        "What is included, drawn from the deliverables in the supplied scope. Do "
        "not add a deliverable that is not in the scope."
    ),
    "milestones": (
        "The milestone sequence and what acceptance means at each one, from the "
        "supplied milestones. Preserve their order."
    ),
    "assumptions": (
        "The assumptions the engagement depends on and what is excluded, from the "
        "supplied assumptions and exclusions. Flag any that need client confirmation."
    ),
    "options": (
        "The core engagement and the optional additions, described as choices. "
        "Describe what each option changes, never what it costs."
    ),
    "pricing": (
        "Framing prose only: how the quote is structured, what drives the "
        "quantities, and which lines are optional. State no figures whatsoever."
    ),
    "payment_schedule": (
        "Framing prose only: how payment relates to milestone acceptance and "
        "invoicing. State no figures and no percentages whatsoever."
    ),
    "case_studies": (
        "A comparable engagement. Every outcome stated here must cite an approved "
        "claim. If no claim supports an outcome, describe the work without one."
    ),
    "next_steps": (
        "What happens on signature, in the first weeks, and who is responsible. "
        "Procedural, not persuasive."
    ),
    "rfp_answers": (
        "Direct answers to the supplied requirements. One block per requirement "
        "where possible. Answer only what the context supports."
    ),
}


def _context(request: GenerateDraftRequest) -> dict[str, Any]:
    """Only the fields a drafting decision depends on, so the prompt stays bounded."""
    return {
        "opportunity": (
            request.opportunity.model_dump(by_alias=True) if request.opportunity else None
        ),
        "discovery": [d.model_dump(by_alias=True) for d in request.discovery],
        "requirements": [r.model_dump(by_alias=True) for r in request.requirements],
        "scope": request.scope.model_dump(by_alias=True) if request.scope else None,
        "approvedClaims": [c.model_dump(by_alias=True) for c in request.approved_claims],
    }


def prompt_for(section_key: str, request: GenerateDraftRequest) -> str:
    if section_key not in SECTION_KEYS:
        raise ValueError(f"unknown section {section_key!r}; expected one of {SECTION_KEYS}")
    context = json.dumps(_context(request), indent=2, sort_keys=True, default=str)
    claim_ids = [c.id for c in request.approved_claims]
    return (
        f"Draft the `{section_key}` section.\n\n"
        f"Brief: {_SECTION_BRIEFS[section_key]}\n\n"
        f"The only claim ids you may cite are: {claim_ids or 'none — cite nothing'}.\n\n"
        f"Context:\n```json\n{context}\n```"
    )
