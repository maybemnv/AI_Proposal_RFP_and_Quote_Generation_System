"""FastAPI dependencies shared by the route modules.

The API deliberately keeps dependency seams small: tests can provide an engine,
clock, and renderer while the domain and persistence code remain real.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.adapters.documents import DocumentRenderAdapter
from app.adapters.storage import storage_from_env
from app.persistence.session import get_engine, session_scope
from app.runtime import is_local_fixture


def db(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    if engine is None:
        engine = get_engine()
        request.app.state.engine = engine
    with session_scope(engine) as session:
        yield session


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def current_actor(
    authorization: str | None = Header(default=None),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, str | None]:
    if is_local_fixture():
        return {"type": "user", "id": x_actor_id or "demo-user"}
    expected = os.getenv("PRODUCTION_API_TOKEN")
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="authenticated actor required")
    return {
        "type": "user",
        "id": os.getenv("PRODUCTION_ACTOR_ID", "authenticated-user"),
    }


def render_adapter() -> DocumentRenderAdapter:
    return DocumentRenderAdapter(storage=storage_from_env())
