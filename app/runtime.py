"""Runtime environment boundaries for the local fixture and deploy targets."""

from __future__ import annotations

import os
from enum import StrEnum
from urllib.parse import urlparse


class EnvironmentConfigurationError(ValueError):
    """Raised when a runtime selects an unsafe or unsupported environment."""


class AppEnvironment(StrEnum):
    LOCAL_FIXTURE = "local-fixture"
    STAGING = "staging"
    PRODUCTION = "production"


def get_app_environment() -> AppEnvironment:
    value = os.getenv("APP_ENV", "production").strip().lower()
    try:
        return AppEnvironment(value)
    except ValueError as exc:
        raise EnvironmentConfigurationError(
            "APP_ENV must be local-fixture, staging, or production"
        ) from exc


def is_local_fixture() -> bool:
    return get_app_environment() is AppEnvironment.LOCAL_FIXTURE


def fixture_only_message() -> str:
    return "fixture-only behavior requires APP_ENV=local-fixture"


def cors_origins() -> list[str]:
    environment = get_app_environment()
    raw = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3106" if environment is AppEnvironment.LOCAL_FIXTURE else "",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if environment is not AppEnvironment.LOCAL_FIXTURE:
        local_origins = {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        if any(urlparse(origin).hostname in local_origins for origin in origins):
            raise EnvironmentConfigurationError(
                "localhost CORS origins are only allowed in APP_ENV=local-fixture"
            )
    return origins


def validate_generation_mode(mode: str) -> None:
    normalized = mode.strip().lower()
    if normalized == "claude":
        return
    if not is_local_fixture():
        raise EnvironmentConfigurationError(fixture_only_message())


def validate_runtime() -> None:
    if not is_local_fixture():
        raise EnvironmentConfigurationError(
            "proposal runtime is fixture-only; use APP_ENV=local-fixture"
        )
