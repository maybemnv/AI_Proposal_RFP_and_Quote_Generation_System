"""FastAPI dependencies shared by the route modules.

The API deliberately keeps dependency seams small: tests can provide an engine,
clock, and renderer while the domain and persistence code remain real.
"""

from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import Header, Request
from sqlalchemy.orm import Session

from app.adapters.documents import DocumentRenderAdapter
from app.persistence.session import get_engine, session_scope


def db(request: Request) -> Iterator[Session]:
    engine = request.app.state.engine
    if engine is None:
        engine = get_engine()
        request.app.state.engine = engine
    with session_scope(engine) as session:
        yield session


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def current_actor(
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict[str, str | None]:
    return {"type": "user", "id": x_actor_id or "demo-user"}


def render_adapter() -> DocumentRenderAdapter:
    return DocumentRenderAdapter()
