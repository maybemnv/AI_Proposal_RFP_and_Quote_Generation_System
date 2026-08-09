"""Engine resolution. The pooler branch exists because a hosted Postgres
connection string is the deployment default, and psycopg3's automatic prepared
statements break behind a transaction-mode pooler on the fifth identical query —
late enough to pass local testing and fail in front of a client."""

from sqlalchemy.pool import NullPool

from app.persistence.session import DEFAULT_URL, engine_kwargs, get_engine

DIRECT = "postgresql+psycopg://u:p@db.example.supabase.co:5432/postgres"
POOLED = "postgresql+psycopg://u:p@aws-0-us-east-1.pooler.example.com:6543/postgres"


def test_explicit_url_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DIRECT)
    assert get_engine("sqlite+pysqlite:///:memory:").url.drivername == "sqlite+pysqlite"


def test_database_url_is_used_when_no_argument_is_given(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DIRECT)
    assert get_engine().url.host == "db.example.supabase.co"


def test_compose_default_is_the_last_resort(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_engine().url.render_as_string(hide_password=False) == DEFAULT_URL


def test_direct_connection_keeps_sqlalchemy_pooling():
    assert engine_kwargs(DIRECT) == {"future": True}
    assert not isinstance(get_engine(DIRECT).pool, NullPool)


def test_pooled_connection_disables_prepared_statements_and_defers_pooling():
    assert engine_kwargs(POOLED)["connect_args"] == {"prepare_threshold": None}
    assert isinstance(get_engine(POOLED).pool, NullPool)


def test_sqlite_is_never_treated_as_pooled():
    """The in-memory test engine must not pick up psycopg connect args."""
    assert engine_kwargs("sqlite+pysqlite:///:memory:") == {"future": True}
