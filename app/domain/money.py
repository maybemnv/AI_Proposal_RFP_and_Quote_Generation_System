"""Integer minor units only. Floating point pricing is prohibited (I9)."""

from decimal import Decimal, ROUND_HALF_UP


class MoneyError(ValueError):
    """Raised when a money value would lose precision or use floating point."""


def to_minor(amount: str | int | Decimal, exponent: int = 2) -> int:
    if isinstance(amount, float):
        raise MoneyError("floating point money is prohibited (I9)")
    value = amount if isinstance(amount, Decimal) else Decimal(amount)
    scaled = (value * (10**exponent)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(scaled)


def format_minor(minor: int, currency: str = "USD", exponent: int = 2) -> str:
    if not isinstance(minor, int) or isinstance(minor, bool):
        raise MoneyError("minor units must be int")
    sign = "-" if minor < 0 else ""
    digits = str(abs(minor)).rjust(exponent + 1, "0")
    whole, frac = digits[:-exponent], digits[-exponent:]
    return f"{sign}{int(whole):,}.{frac} {currency}"


def line_subtotal_minor(unit_price_minor: int, quantity: Decimal) -> int:
    if not isinstance(unit_price_minor, int) or isinstance(unit_price_minor, bool):
        raise MoneyError("unit price must be int minor units")
    if isinstance(quantity, float):
        raise MoneyError("floating point quantity is prohibited (I9)")
    qty = quantity if isinstance(quantity, Decimal) else Decimal(quantity)
    product = (Decimal(unit_price_minor) * qty).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(product)
