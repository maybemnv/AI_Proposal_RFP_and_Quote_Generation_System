from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.adapters.generation import get_generation_adapter
from app.api.deps import current_actor
from app.api.main import create_app
from app.runtime import EnvironmentConfigurationError, validate_runtime


def test_demo_runbook_selects_fixture_environment_for_direct_commands():
    runbook = (Path(__file__).parents[2] / "docs" / "DEMO_RUNBOOK.md").read_text(encoding="utf-8")

    assert '$env:APP_ENV = "local-fixture"; python -m app.cli reset' in runbook
    assert '$env:APP_ENV = "local-fixture"; $env:DATABASE_URL' in runbook
    assert '$env:NEXT_PUBLIC_APP_ENV = "local-fixture"' in runbook


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


def test_production_reads_require_the_server_auth_boundary(engine, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://server-only")
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "private-documents")
    monkeypatch.setenv("PRODUCTION_API_TOKEN", "server-token")

    response = TestClient(create_app(engine=engine)).get("/v1/opportunities")

    assert response.status_code == 401
