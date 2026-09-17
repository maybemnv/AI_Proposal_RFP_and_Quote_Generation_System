import pytest
from fastapi import HTTPException

from app.adapters.generation import get_generation_adapter
from app.api.deps import current_actor
from app.runtime import EnvironmentConfigurationError, validate_runtime
from app.api.main import create_app


def test_fixture_reset_is_unavailable_outside_local_fixture(engine, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(EnvironmentConfigurationError, match="PostgreSQL"):
        create_app(engine=engine)


def test_fixture_generation_is_rejected_outside_local_fixture(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("GENERATION_MODE", "fixture")

    with pytest.raises(EnvironmentConfigurationError, match="local-fixture"):
        get_generation_adapter()


def test_production_runtime_requires_durable_dependencies(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unsafe.db")
    with pytest.raises(EnvironmentConfigurationError, match="PostgreSQL"):
        validate_runtime()


def test_production_actor_does_not_trust_browser_actor_header(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PRODUCTION_API_TOKEN", "server-token")
    with pytest.raises(HTTPException) as error:
        current_actor(authorization=None, x_actor_id="admin")
    assert error.value.status_code == 401
