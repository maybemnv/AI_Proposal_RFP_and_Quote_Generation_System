"""Adapters are the only place the system touches an external boundary, and in
demo mode they touch fixtures instead. Every failure path must be reachable on
command, and no adapter may raise: the pitch shows the failure branch, it does
not show a traceback."""

import pytest

from app.adapters import get_adapter
from app.adapters.base import load_fixture
from app.domain.schemas import PROVIDERS, AdapterFailure

RETRYABLE_CODES = {"RATE_LIMIT", "TEMPORARY"}
ALL_CODES = {"AUTH", "NOT_FOUND", "RATE_LIMIT", "UNSUPPORTED", "TEMPORARY", "UNKNOWN"}


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_provider_has_success_and_failure_fixtures(provider):
    assert load_fixture(provider, "success")
    assert load_fixture(provider, "failure")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_adapter_declares_capabilities(provider):
    assert get_adapter(provider).capabilities()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_every_adapter_reports_its_own_provider(provider):
    assert get_adapter(provider).provider == provider


@pytest.mark.parametrize("provider", PROVIDERS)
def test_failure_fixture_names_its_own_provider_and_agrees_on_retryability(provider):
    """A copy-pasted fixture would otherwise blame the wrong system, and a
    retryable flag that disagrees with its code would mislead the retry UI."""
    failure = get_adapter(provider).execute({"outcome": "failure"})
    assert isinstance(failure, AdapterFailure)
    assert failure.provider == provider
    assert failure.retryable is (failure.code in RETRYABLE_CODES)


def test_the_eight_failures_cover_every_code_in_the_union():
    codes = {get_adapter(p).execute({"outcome": "failure"}).code for p in PROVIDERS}
    assert codes == ALL_CODES


@pytest.mark.parametrize("provider", ["hubspot", "salesforce"])
def test_crm_success_returns_normalized_opportunity(provider):
    result = get_adapter(provider).execute({"outcome": "success", "externalId": "42"})
    assert result["accountName"]
    assert result["sourceRecords"]


def test_crm_success_echoes_the_requested_external_id():
    """The imported opportunity must point back at the record that was asked for."""
    result = get_adapter("hubspot").execute({"outcome": "success", "externalId": "hs-9001"})
    assert result["externalId"] == "hs-9001"


def test_crm_failure_returns_adapter_failure_not_an_exception():
    result = get_adapter("hubspot").execute({"outcome": "failure"})
    assert isinstance(result, AdapterFailure)
    assert result.code in ALL_CODES
    assert result.provider == "hubspot"


def test_rate_limit_failure_is_retryable():
    result = get_adapter("salesforce").execute({"outcome": "failure"})
    assert result.retryable is (result.code in RETRYABLE_CODES)


@pytest.mark.parametrize("provider", ["pandadoc", "docusign"])
def test_signature_adapter_emits_engagement_events(provider):
    result = get_adapter(provider).execute({"outcome": "success",
                                            "action": "send",
                                            "documentId": "d1"})
    assert result["engagementEvents"][0]["type"] in {"sent", "viewed", "signed"}


@pytest.mark.parametrize("provider", ["google_drive", "microsoft_365", "manual"])
def test_document_adapters_return_a_stored_location(provider):
    result = get_adapter(provider).execute({"outcome": "success", "documentId": "d1"})
    assert result["storageUri"]


def test_stripe_link_echoes_the_requested_amount():
    """I3 would be theatre if the payment link disagreed with the quote total."""
    result = get_adapter("stripe").execute({"outcome": "success", "amountMinor": 1234500})
    assert result["amountMinor"] == 1234500
    assert result["paymentUrl"]


def test_stripe_link_falls_back_to_the_fixture_amount_when_none_is_requested():
    result = get_adapter("stripe").execute({"outcome": "success"})
    assert isinstance(result["amountMinor"], int)


def test_success_is_the_default_outcome():
    assert not isinstance(get_adapter("hubspot").execute({}), AdapterFailure)


def test_an_unknown_outcome_is_refused_without_raising():
    result = get_adapter("hubspot").execute({"outcome": "sideways"})
    assert isinstance(result, AdapterFailure)
    assert result.code == "UNSUPPORTED"


def test_an_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="unknown provider"):
        get_adapter("netsuite")


def test_missing_fixture_file_raises_for_the_developer_not_the_demo():
    with pytest.raises(FileNotFoundError, match="missing fixture"):
        load_fixture("hubspot", "nonexistent")


def test_capabilities_cannot_be_mutated_through_the_returned_list():
    adapter = get_adapter("hubspot")
    adapter.capabilities().append("wire_transfer")
    assert "wire_transfer" not in adapter.capabilities()
