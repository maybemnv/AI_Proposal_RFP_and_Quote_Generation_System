from decimal import Decimal

import pytest

from app.domain.money import MoneyError, format_minor, line_subtotal_minor, to_minor


def test_to_minor_from_string():
    assert to_minor("1250.00") == 125000
    assert to_minor("0.01") == 1


def test_to_minor_rejects_float():
    with pytest.raises(MoneyError):
        to_minor(1250.00)


def test_to_minor_rounds_half_up():
    assert to_minor("0.005") == 1


def test_format_minor():
    assert format_minor(125000) == "1,250.00 USD"
    assert format_minor(-500, "EUR") == "-5.00 EUR"


def test_format_minor_rejects_non_int():
    with pytest.raises(MoneyError):
        format_minor(1250.0)


def test_line_subtotal_fractional_quantity():
    assert line_subtotal_minor(120000, Decimal("2.5")) == 300000


def test_line_subtotal_rejects_float_quantity():
    with pytest.raises(MoneyError):
        line_subtotal_minor(120000, 2.5)
