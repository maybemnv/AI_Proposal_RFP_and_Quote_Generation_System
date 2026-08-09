"""Pricing calculation endpoint."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.api.utils import dump, flag, flags_response, not_found
from app.domain.audit import record_event
from app.domain.pricing import PricingError, calculate_quote
from app.domain.workflow import TransitionError, assert_mutable
from app.persistence.repositories import (
    DiscountPolicyRepo,
    OpportunityRepo,
    PricingRuleRepo,
    ProposalRepo,
    VersionRepo,
)

router = APIRouter()


@router.post("/proposal-versions/{version_id}/quote/calculate")
def calculate(
    version_id: str,
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    version = VersionRepo(session).find(version_id)
    if version is None:
        return not_found("proposal version", version_id)
    try:
        assert_mutable(version)
    except TransitionError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])])
    proposal = ProposalRepo(session).find(version.proposal_id)
    opportunity = OpportunityRepo(session).find(proposal.opportunity_id) if proposal else None
    if opportunity is None:
        return not_found("opportunity", "")
    rules = {item.id: item for item in PricingRuleRepo(session).list()}
    raw_lines = []
    for raw in body.get("lines", []):
        raw_lines.append({
            "id": raw["id"], "label": raw["label"], "ruleId": raw["ruleId"],
            "quantity": Decimal(str(raw["quantity"])),
            "optional": raw.get("optional", True),
            "selected": raw.get("selected", True),
            "sourceRecordIds": raw.get("sourceRecordIds", []),
        })
    try:
        quote = calculate_quote(
            raw_lines, rules, body.get("currency", opportunity.currency),
            discount_minor=int(body.get("discountMinor", 0)),
            tax_minor=int(body.get("taxMinor", 0)),
            installments=body.get("installments", []), calculated_at=clock,
        )
    except (KeyError, PricingError, TypeError, ValueError) as exc:
        return flags_response([flag("PRICE_MISMATCH", str(exc), [version_id])])
    policy = None
    for line in quote.lines:
        rule = rules.get(line.rule_id)
        if rule and rule.discount_policy_id:
            policy = DiscountPolicyRepo(session).find(rule.discount_policy_id)
            if policy:
                break
    discount_percent = (quote.discount_minor / quote.subtotal_minor * 100) if quote.subtotal_minor else 0
    requires_review = bool(policy and (
        quote.discount_minor > policy.max_minor_without_approval
        or discount_percent > policy.max_percent_without_approval
        or quote.total_minor > policy.requires_quote_approval_above
    ))
    status = "review_required" if requires_review else "calculated"
    message = "discount or total requires quote approval" if requires_review else None
    VersionRepo(session).update(version.model_copy(update={"quote": quote, "unresolved_flags": []}))
    record_event(
        session, workspace_id="workspace-demo", actor_type=actor["type"],
        actor_id=actor["id"], action="edited", entity_type="proposal",
        entity_id=version_id, after_hash=quote.input_hash, created_at=clock,
    )
    return dump(quote) | {"status": status, "policyMessage": message}
