# Production-ready repository baseline

The fixture demo remains `APP_ENV=local-fixture`, SQLite, local storage, and
fixture generation. Staging and production fail fast unless PostgreSQL,
private S3-compatible storage, and the server-side bearer token boundary are
configured.

```powershell
$env:APP_ENV = "staging"
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require"
$env:STORAGE_BACKEND = "s3"
$env:S3_BUCKET = "private-proposal-documents"
$env:PRODUCTION_API_TOKEN = "set-in-deployment-secret-manager"
uv run alembic upgrade head
uv run uvicorn app.api.main:app --host 0.0.0.0 --port $env:PORT
```

`/health` is readiness-oriented and returns 503 until the configured database
contains proposal data. The API does not seed or reset production data. PDF
objects use opaque private keys and downloads are short-lived signed redirects.
Set `GENERATION_MODE=claude` only when the server-side Anthropic secret is
available; generation failure leaves the proposal recoverable.

This is a production-ready repository baseline, not a live infrastructure or
provider verification. Configure backups, retention/deletion, TLS, monitoring,
and approval-role provisioning before promotion.
