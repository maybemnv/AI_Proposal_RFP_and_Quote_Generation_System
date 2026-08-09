"""Adapter registry. ``get_adapter`` is the only way callers reach a provider.

The registry is keyed by the PRD's provider union and asserted complete at import
time, so adding a provider to the contract without adding its adapter fails
immediately rather than at the first request in a demo.
"""

from app.adapters.base import AdapterFailure, FixtureAdapter, ProviderAdapter, load_fixture
from app.adapters.crm import HubspotAdapter, SalesforceAdapter
from app.adapters.documents import DriveAdapter, M365Adapter
from app.adapters.payments import StripeAdapter
from app.adapters.signatures import DocuSignAdapter, PandaDocAdapter
from app.adapters.sources import ManualAdapter
from app.domain.schemas import PROVIDERS

_REGISTRY: dict[str, ProviderAdapter] = {
    "hubspot": HubspotAdapter(),
    "salesforce": SalesforceAdapter(),
    "pandadoc": PandaDocAdapter(),
    "docusign": DocuSignAdapter(),
    "stripe": StripeAdapter(),
    "google_drive": DriveAdapter(),
    "microsoft_365": M365Adapter(),
    "manual": ManualAdapter(),
}

_missing = set(PROVIDERS) - set(_REGISTRY)
if _missing:
    raise RuntimeError(f"providers declared in the contract have no adapter: {_missing}")


def get_adapter(provider: str) -> ProviderAdapter:
    try:
        return _REGISTRY[provider]
    except KeyError:
        raise ValueError(
            f"unknown provider {provider!r}; expected one of {sorted(_REGISTRY)}"
        ) from None


__all__ = [
    "AdapterFailure",
    "DocuSignAdapter",
    "DriveAdapter",
    "FixtureAdapter",
    "HubspotAdapter",
    "M365Adapter",
    "ManualAdapter",
    "PandaDocAdapter",
    "ProviderAdapter",
    "SalesforceAdapter",
    "StripeAdapter",
    "get_adapter",
    "load_fixture",
]
