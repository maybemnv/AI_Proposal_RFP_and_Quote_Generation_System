# Proposal Workflow Prototype

This repository is a deterministic prototype for turning CRM/RFP source material into a source-linked proposal, a rule-backed quote, role-gated approvals, a rendered PDF, delivery, and post-send engagement analytics.

The default demo mode is fixture-backed. It needs no provider credentials and keeps the same contracts used by live generation and provider adapters.

## Fixture showcase quick start

The supported showcase runs entirely from deterministic fixtures: no Docker, paid
credentials, or live provider accounts are required. Copy `.env.example` to
`.env`, then install the project and browser dependencies.

```powershell
python -m pip install -e ".[dev]"
python -m playwright install chromium
cd app/web
npm ci
cd ../..
```

Reset the local fixture database before the demo:

```powershell
python -m app.cli reset
```

Start the API and web shell in two PowerShell terminals from the repository root.

```powershell
# Terminal 1
$env:DATABASE_URL = "sqlite+pysqlite:///var/showcase.db"
$env:STORAGE_DIR = "var/documents"
uvicorn app.api.main:app --port 8106

# Terminal 2
cd app/web
npm run dev
```

Open `http://localhost:3106`. Confirm the fixture is ready before presenting it:

```powershell
Invoke-RestMethod http://localhost:8106/health
# expected: @{status=running; ready=True}
```

The API returns HTTP 503 with `ready: false` when the fixture database is missing
or unseeded. The rendered PDF is stored locally under `var/documents/`.

## Verification

```powershell
python -m pytest -q
ruff check app/
cd app/web
npm run build
npm run e2e
```

The browser suite owns a clean SQLite fixture lifecycle, checks the downloaded
artifact begins with `%PDF`, and includes desktop and narrow-mobile Trace A
coverage. `python -m app.cli demo` is also available as a terminal fallback and
writes a fixture PDF under `var/storage/`.

## Workflow screens

- `/opportunities` — import and normalize source opportunities, including adapter failures.
- `/proposals/prop_northwind` — source-linked draft editor and evidence rail.
- `/proposals/prop_northwind/scope` — deliverables, milestones, assumptions, exclusions, and open questions.
- `/proposals/prop_northwind/quote` — server-shaped pricing lines, options, policy review, and payment schedule.
- `/proposals/prop_northwind/approval` — role-gated approval cards and locking.
- `/proposals/prop_northwind/preview` — client document preview and PDF download.
- `/content` — claim approval, validity windows, evidence, and expiry blocking.
- `/analytics` — KPI tiles, provider timeline, and one-series views chart with table view.

See [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md) for the click-by-click pitch script and fallback procedure.

## Scope boundaries

Fixture mode is intentionally the reliable demo path. Live generation remains
optional and unverified: use `GENERATION_MODE=claude` and set
`ANTHROPIC_API_KEY` only in a local, uncommitted `.env`. Auth, tenant
provisioning, migrations, live provider credentials, multi-currency, and
production deployment are outside this prototype.
