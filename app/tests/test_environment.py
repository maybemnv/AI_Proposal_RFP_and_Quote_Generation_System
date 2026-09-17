import pytest

from app.adapters.generation import get_generation_adapter
from app.api.main import create_app
from app.runtime import EnvironmentConfigurationError


def test_fixture_reset_is_unavailable_outside_local_fixture(engine, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(EnvironmentConfigurationError, match="local-fixture"):
        create_app(engine=engine)


def test_fixture_generation_is_rejected_outside_local_fixture(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("GENERATION_MODE", "fixture")

    with pytest.raises(EnvironmentConfigurationError, match="local-fixture"):
        get_generation_adapter()
