"""Engine and session plumbing.

``expire_on_commit=False`` matters here: repositories hand back Pydantic models
built from row attributes, and the default would expire those attributes at
commit and re-fetch them off a closed session.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "postgresql+psycopg://proposal:proposal@localhost:5432/proposal"


def get_engine(url: str | None = None) -> Engine:
    """Resolve in order: explicit argument, DATABASE_URL, then the compose default."""
    resolved = url or os.environ.get("DATABASE_URL") or DEFAULT_URL
    return create_engine(resolved, future=True)


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
