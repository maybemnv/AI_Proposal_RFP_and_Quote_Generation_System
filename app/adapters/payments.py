"""Payment-link creation.

The link echoes the amount the caller asked for. A link that disagreed with the
quote total would make I3 theatre: the arithmetic would be exact on screen and
wrong at checkout.
"""

from app.adapters.base import FixtureAdapter


class StripeAdapter(FixtureAdapter):
    provider = "stripe"
    _capabilities = ("create_payment_link", "fetch_payment_status")
    _echo_keys = ("amountMinor", "currency", "documentId")
