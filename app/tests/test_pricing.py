from decimal import Decimal

import pytest

from app.domain.pricing import PricingError, calculate_quote, compute_input_hash
from app.domain.schemas import PricingRule

NOW = "2026-08-01T00:00:00Z"


def rule(id_="r1", price=120000, unit="day", min_q=1, max_q=None,
         active_from="2026-01-01", active_until=None, optional=False):
    return PricingRule(
        id=id_, version="2026.1", label="Senior consulting", unit=unit,
        currency="USD", unit_price_minor=price, min_quantity=min_q,
        max_quantity=max_q, optional=optional, active_from=active_from,
        active_until=active_until, source_record_ids=[],
    )


def line(id_="l1", rule_id="r1", qty="2", optional=False, selected=True):
    return {"id": id_, "label": "Senior consulting", "ruleId": rule_id,
            "quantity": Decimal(qty), "optional": optional,
            "selected": selected, "sourceRecordIds": []}


def test_step1_mixed_currency_rejected():
    eur = rule("r2").model_copy(update={"currency": "EUR"})
    with pytest.raises(PricingError, match="currency"):
        calculate_quote([line(), line("l2", "r2")], {"r1": rule(), "r2": eur},
                        "USD", calculated_at=NOW)


def test_step1_unknown_rule_rejected():
    with pytest.raises(PricingError, match="unknown pricing rule"):
        calculate_quote([line(rule_id="nope")], {"r1": rule()}, "USD",
                        calculated_at=NOW)


def test_step2_quantity_below_minimum_rejected():
    with pytest.raises(PricingError, match="quantity"):
        calculate_quote([line(qty="0")], {"r1": rule(min_q=1)}, "USD", calculated_at=NOW)


def test_step2_quantity_above_maximum_rejected():
    with pytest.raises(PricingError, match="quantity"):
        calculate_quote([line(qty="9")], {"r1": rule(max_q=5)}, "USD", calculated_at=NOW)


def test_step2_fractional_bound_is_compared_without_float_drift():
    # Decimal(0.1) is 0.1000...0055511151231257827; Decimal("0.1") is not.
    q = calculate_quote([line(qty="0.1")], {"r1": rule(min_q=0.1)}, "USD",
                        calculated_at=NOW)
    assert q.lines[0].subtotal_minor == 12000


def test_step2_inactive_rule_rejected():
    with pytest.raises(PricingError, match="active"):
        calculate_quote([line()], {"r1": rule(active_until="2026-01-31")},
                        "USD", calculated_at=NOW)


def test_step3_line_subtotal_is_quantity_times_unit_price():
    q = calculate_quote([line(qty="2")], {"r1": rule()}, "USD", calculated_at=NOW)
    assert q.lines[0].subtotal_minor == 240000


def test_step4_unselected_optional_line_is_excluded():
    q = calculate_quote(
        [line(), line("l2", "r1", "1", optional=True, selected=False)],
        {"r1": rule()}, "USD", calculated_at=NOW)
    assert q.subtotal_minor == 240000


def test_step4_selected_optional_line_is_included():
    q = calculate_quote(
        [line(), line("l2", "r1", "1", optional=True, selected=True)],
        {"r1": rule()}, "USD", calculated_at=NOW)
    assert q.subtotal_minor == 360000


def test_step6_total_formula():
    q = calculate_quote([line()], {"r1": rule()}, "USD",
                        discount_minor=40000, tax_minor=10000, calculated_at=NOW)
    assert q.total_minor == 240000 - 40000 + 10000


def test_step6_negative_total_rejected():
    with pytest.raises(PricingError, match="negative"):
        calculate_quote([line()], {"r1": rule()}, "USD",
                        discount_minor=999999, calculated_at=NOW)


def test_step7_installments_must_sum_to_total():
    with pytest.raises(PricingError, match="installment"):
        calculate_quote([line()], {"r1": rule()}, "USD", calculated_at=NOW,
                        installments=[{"sequence": 1, "label": "Deposit",
                                       "amountMinor": 100000,
                                       "dueDescription": "On signature"}])


def test_step7_valid_installments_accepted():
    q = calculate_quote([line()], {"r1": rule()}, "USD", calculated_at=NOW,
                        installments=[
                            {"sequence": 1, "label": "Deposit", "amountMinor": 120000,
                             "dueDescription": "On signature"},
                            {"sequence": 2, "label": "Final", "amountMinor": 120000,
                             "dueDescription": "On delivery"}])
    assert sum(i.amount_minor for i in q.payment_schedule) == q.total_minor


def test_step8_line_carries_rule_version_and_hash_is_stable():
    a = calculate_quote([line()], {"r1": rule()}, "USD", calculated_at=NOW)
    b = calculate_quote([line()], {"r1": rule()}, "USD", calculated_at=NOW)
    assert a.pricing_rule_version == "2026.1"
    assert a.lines[0].rule_id == "r1"
    assert a.input_hash == b.input_hash


def test_hash_changes_when_input_changes():
    a = calculate_quote([line(qty="2")], {"r1": rule()}, "USD", calculated_at=NOW)
    b = calculate_quote([line(qty="3")], {"r1": rule()}, "USD", calculated_at=NOW)
    assert a.input_hash != b.input_hash


def test_hash_is_insensitive_to_key_order():
    assert compute_input_hash({"a": 1, "b": 2}) == compute_input_hash({"b": 2, "a": 1})


def test_recomputing_from_a_stored_float_quantity_reproduces_the_hash():
    """Task 10's PRICE_MISMATCH check depends on this round-trip holding."""
    first = calculate_quote([line(qty="2.5")], {"r1": rule()}, "USD", calculated_at=NOW)
    stored = first.lines[0]
    replay = line(qty=str(Decimal(str(stored.quantity))))
    second = calculate_quote([replay], {"r1": rule()}, "USD", calculated_at=NOW)
    assert second.input_hash == first.input_hash
    assert second.total_minor == first.total_minor


def test_float_quantity_rejected():
    bad = line()
    bad["quantity"] = 2.0
    with pytest.raises(PricingError, match="Decimal"):
        calculate_quote([bad], {"r1": rule()}, "USD", calculated_at=NOW)


def test_lines_spanning_two_rule_versions_are_rejected():
    v2 = rule("r2").model_copy(update={"version": "2026.2"})
    with pytest.raises(PricingError, match="version"):
        calculate_quote([line(), line("l2", "r2")], {"r1": rule(), "r2": v2},
                        "USD", calculated_at=NOW)

