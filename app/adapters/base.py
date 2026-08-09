"""Every external boundary is an adapter with fixtures, so the demo needs no
credentials and no network.

Two rules hold for every adapter:

1. **It never raises on a request.** A bad outcome, an unsupported action, a
   provider that is down — all of them come back as ``AdapterFailure``. The
   pitch demonstrates failure branches on command; it does not demonstrate
   tracebacks.
2. **It never invents data.** Success payloads come from the fixture on disk.
   Adapters may echo a value the caller supplied (an external id, an amount)
   so the demo stays coherent, but they do not synthesize new facts.

A missing fixture *file* is different: that is a packaging bug, not a runtime
outcome, so ``load_fixture`` raises for the developer.
"""

import json
from pathlib import Path
from typing import Any, Protocol

from app.domain.schemas import AdapterFailure

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "providers"

OUTCOMES = ("success", "failure")


def load_fixture(provider: str, outcome: str) -> dict[str, Any]:
    path = FIXTURE_ROOT / provider / f"{outcome}.json"
    if not path.exists():
        raise FileNotFoundError(f"missing fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


class ProviderAdapter(Protocol):
    provider: str

    def capabilities(self) -> list[str]: ...
    def execute(self, request: dict[str, Any]) -> dict[str, Any] | AdapterFailure: ...


class FixtureAdapter:
    """Base for demo-mode adapters. Returns AdapterFailure; never raises."""

    provider: str = "manual"
    _capabilities: tuple[str, ...] = ()
    _echo_keys: tuple[str, ...] = ()

    def capabilities(self) -> list[str]:
        return list(self._capabilities)

    def execute(self, request: dict[str, Any]) -> dict[str, Any] | AdapterFailure:
        outcome = request.get("outcome", "success")
        if outcome not in OUTCOMES:
            return AdapterFailure(
                code="UNSUPPORTED",
                provider=self.provider,
                message=f"unsupported outcome {outcome!r}; expected one of {OUTCOMES}",
                retryable=False,
            )
        payload = load_fixture(self.provider, outcome)
        if outcome == "failure":
            return AdapterFailure.model_validate(payload)
        return self._on_success(payload, request)

    def _on_success(
        self, payload: dict[str, Any], request: dict[str, Any]
    ) -> dict[str, Any]:
        """Echo caller-supplied values named in ``_echo_keys`` into the payload,
        so a fixture answer still refers to what was actually asked for. Keys the
        caller omitted keep the fixture's own value."""
        echoed = {key: request[key] for key in self._echo_keys
                  if request.get(key) is not None}
        return {**payload, **echoed} if echoed else payload
