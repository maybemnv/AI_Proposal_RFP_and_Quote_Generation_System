"""Engine and session plumbing.

``expire_on_commit=False`` matters here: repositories hand back Pydantic models
built from row attributes, and the default would expire those attributes at
commit and re-fetch them off a closed session.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, NullPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "postgresql+psycopg://proposal:proposal@localhost:5432/proposal"

POOLER_PORTS = frozenset({"6543"})


def _is_pooled(url: str) -> bool:
    """A PgBouncer transaction-mode pooler, as used by hosted Postgres (Supabase's
    port 6543 pooler, and the same shape elsewhere)."""
    return any(f":{port}/" in url for port in POOLER_PORTS)


def engine_kwargs(url: str) -> dict[str, Any]:
    """The engine options a given URL needs. Split out from ``get_engine`` so the
    decision is directly testable — SQLAlchemy captures ``connect_args`` inside a
    pool closure, where a test cannot see it."""
    if not _is_pooled(url):
        return {"future": True}
    return {
        "future": True,
        "poolclass": NullPool,
        "connect_args": {"prepare_threshold": None},
    }


def get_engine(url: str | None = None) -> Engine:
    """Resolve in order: explicit argument, DATABASE_URL, then the compose default.

    Behind a transaction-mode pooler, server-side prepared statements are not
    safe: the pooler hands the next statement to a different backend session,
    which has never seen the prepared name. psycopg3 prepares automatically after
    a few executions, so this fails on the *fifth* identical query rather than
    the first — the kind of bug that passes local testing and surfaces in a demo.
    Disabling the prepare threshold and using NullPool leaves pooling to the
    pooler, which is what it is there for.
    """
    resolved = url or os.environ.get("DATABASE_URL") or DEFAULT_URL
    return create_engine(resolved, **engine_kwargs(resolved))


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
