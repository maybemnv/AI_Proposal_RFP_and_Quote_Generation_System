"""Deterministic pricing. Same inputs, same rule versions, same output (I2, I3, I4, I9).

The eight steps below are the PRD's pricing algorithm in order. Each raises
``PricingError`` rather than returning a partial quote: a quote that silently
dropped an out-of-bounds line would be worse than no quote at all.

Quantities cross this boundary as ``Decimal``. Callers holding a stored
``QuoteLine.quantity`` (a float, because the wire contract says ``number``) must
convert with ``Decimal(str(qty))`` — never ``Decimal(float)``, which carries the
binary expansion into the hash and breaks the PRICE_MISMATCH recompute.
"""

import hashlib
import json
from decimal import Decimal
from typing import NotRequired, TypedDict

from app.domain.money import line_subtotal_minor
from app.domain.schemas import PaymentInstallment, PricingRule, Quote, QuoteLine


class PricingError(ValueError):
    """Raised when pricing inputs violate a rule, bound, or invariant."""


class QuoteLineInput(TypedDict):
    """An unpriced line. camelCase keys so API payloads pass through unchanged."""

    id: str
    label: str
    ruleId: str
    quantity: Decimal
    optional: NotRequired[bool]
    selected: NotRequired[bool]
    sourceRecordIds: NotRequired[list[str]]


class InstallmentSpec(TypedDict):
    sequence: int
    label: str
    amountMinor: int
    dueDescription: str


def _as_decimal(value: float | str | Decimal) -> Decimal:
    """Bounds arrive from PricingRule as ``number``; route them through str."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


def compute_input_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate_quote(
    lines: list[QuoteLineInput],
    rules: dict[str, PricingRule],
    currency: str,
    *,
    discount_minor: int = 0,
    tax_minor: int = 0,
    installments: list[InstallmentSpec] | None = None,
    calculated_at: str,
) -> Quote:
    # Step 1 — every line shares one currency.
    for raw in lines:
        rule = rules.get(raw["ruleId"])
        if rule is None:
            raise PricingError(f"unknown pricing rule {raw['ruleId']}")
        if rule.currency != currency:
            raise PricingError(f"currency mismatch: {rule.currency} != {currency}")

    day = calculated_at[:10]
    priced: list[QuoteLine] = []
    versions: set[str] = set()

    for raw in lines:
        rule = rules[raw["ruleId"]]
        qty = raw["quantity"]
        if not isinstance(qty, Decimal):
            raise PricingError(f"quantity must be Decimal, got {type(qty).__name__} (I9)")

        # Step 2 — quantity bounds and the rule's active window.
        if qty < _as_decimal(rule.min_quantity):
            raise PricingError(f"quantity {qty} below minimum {rule.min_quantity}")
        if rule.max_quantity is not None and qty > _as_decimal(rule.max_quantity):
            raise PricingError(f"quantity {qty} above maximum {rule.max_quantity}")
        if rule.active_from > day or (rule.active_until is not None and rule.active_until < day):
            raise PricingError(f"rule {rule.id} is not active on {day}")

        # Step 3 — line subtotal from integer unit price and Decimal quantity.
        subtotal = line_subtotal_minor(rule.unit_price_minor, qty)
        selected = raw.get("selected", True)
        if not rule.optional and not selected:
            raise PricingError(f"mandatory pricing rule {rule.id} cannot be deselected")
        versions.add(rule.version)
        priced.append(QuoteLine(
            id=raw["id"], label=raw["label"], rule_id=rule.id, quantity=float(qty),
            unit_price_minor=rule.unit_price_minor, subtotal_minor=subtotal,
            optional=rule.optional, selected=selected,
            source_record_ids=raw.get("sourceRecordIds", []),
        ))

    # Step 4 — only selected lines reach the subtotal (I4).
    subtotal_minor = sum(item.subtotal_minor for item in priced if item.selected)

    # Steps 5 and 6 — the given discount and tax, then the total formula (I3).
    total_minor = subtotal_minor - discount_minor + tax_minor
    if total_minor < 0:
        raise PricingError("negative total is rejected (I3)")

    # Step 7 — installments sum to the total exactly, or there is no schedule.
    schedule = [PaymentInstallment.model_validate(i) for i in (installments or [])]
    if schedule and sum(i.amount_minor for i in schedule) != total_minor:
        raise PricingError("installment amounts must sum exactly to totalMinor")

    # Step 8 — one rule version per quote, then hash the inputs (I2).
    if len(versions) > 1:
        raise PricingError(f"lines span multiple rule versions: {sorted(versions)}")
    input_hash = compute_input_hash({
        "currency": currency,
        "discountMinor": discount_minor,
        "taxMinor": tax_minor,
        "calculatedAt": calculated_at,
        "lines": [{"id": item.id, "ruleId": item.rule_id,
                   "quantity": str(Decimal(str(item.quantity))),
                   "unitPriceMinor": item.unit_price_minor,
                   "optional": item.optional,
                   "selected": item.selected}
                  for item in priced],
    })

    return Quote(
        currency=currency, lines=priced, subtotal_minor=subtotal_minor,
        discount_minor=discount_minor, tax_minor=tax_minor, total_minor=total_minor,
        payment_schedule=schedule, pricing_rule_version=next(iter(versions), "none"),
        input_hash=input_hash, calculated_at=calculated_at,
    )
