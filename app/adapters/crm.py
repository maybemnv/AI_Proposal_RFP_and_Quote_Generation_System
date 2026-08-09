"""CRM adapters. Import normalizes a provider opportunity and carries the source
records that back every imported field, so nothing downstream is unsourced."""

from app.adapters.base import FixtureAdapter


class _CrmAdapter(FixtureAdapter):
    _capabilities = ("import_opportunity", "list_opportunities", "fetch_contact")
    _echo_keys = ("externalId",)


class HubspotAdapter(_CrmAdapter):
    provider = "hubspot"


class SalesforceAdapter(_CrmAdapter):
    provider = "salesforce"
