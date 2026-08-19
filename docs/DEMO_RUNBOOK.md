# Demo Runbook

## Setup once

1. Copy `.env.example` to `.env` and leave `GENERATION_MODE=fixture` for deterministic demos. It selects local SQLite and storage beneath ignored `var/`; no Docker or credential is required.
2. Install Python dependencies: `python -m pip install -e ".[dev]"`.
3. Install the browser used by the renderer and E2E suite: `python -m playwright install chromium`.
4. Install the web dependencies: `cd app/web && npm ci`.

## Before every demo

1. From the repository root, run `python -m app.cli reset`.
2. In terminal 1, run `$env:DATABASE_URL = "sqlite+pysqlite:///var/showcase.db"; $env:STORAGE_DIR = "var/documents"; uvicorn app.api.main:app --port 8106`.
3. In terminal 2, run `cd app/web; npm run dev`. The web shell binds `3106`.
4. Confirm readiness with `Invoke-RestMethod http://localhost:8106/health`; expected response is `status: running` and `ready: true`.
5. Run the smoke path: `cd app/web; npm run e2e -- e2e/trace-a.spec.ts`.
6. If the smoke test is green, open `http://localhost:3106`.

## The pitch path

| # | Screen | What to say | What to click |
|---|---|---|---|
| 1 | `/opportunities` | Nothing is typed twice; the CRM record is the source. | Import from HubSpot. |
| 2 | `/opportunities` | When the source is incomplete we say so instead of guessing. | Switch Outcome to Failure, import, and show `AUTH`. |
| 3 | `/proposals/prop_northwind` | Every client-facing assertion stays close to its evidence. | Click a source chip and show the excerpt. |
| 4 | `/proposals/prop_northwind/scope` | Open questions stay visible until someone answers them. | Resolve the legacy-CMS question. |
| 5 | `/proposals/prop_northwind/quote` | Pricing is deterministic; optional work never inflates the headline. | Toggle Training on and off. |
| 6 | `/proposals/prop_northwind/quote` | Discount authority is enforced, not requested. | Enter `500.00`, recalculate, and show `Review required`. |
| 7 | `/proposals/prop_northwind/approval` | Delivery is impossible until every gate clears. | Show the blocking flag, then approve the required roles. |
| 8 | `/proposals/prop_northwind/preview` | This is exactly what the client sees. | Download the PDF. |
| 9 | `/analytics` | We can see what happened after it left. | Show the provider timeline, views chart, and table toggle. |

## Fallback

If the browser or provider stack is unavailable, run:

```bash
python -m app.cli demo
```

It executes the deterministic Trace A gates and writes the PDF under `var/storage/`.

## Is this live AI?

Fixture mode is the default so the demo is repeatable. To opt into live generation, set `GENERATION_MODE=claude` and provide `ANTHROPIC_API_KEY`. The evidence checks, pricing rules, approval gates, locking, rendering, and delivery contracts remain the same.

## Verify and shut down

Run `python -m pytest -q`, `ruff check app/`, then from `app/web` run `npm run build` and `npm run e2e`. The browser suite validates the downloaded artifact's `%PDF` bytes and its narrow-mobile pricing control. Stop the demo with `Ctrl+C` in both terminals. The SQLite database and PDFs remain only under ignored `var/` and can be replaced by the next `python -m app.cli reset`.

## Evidence and limitations

The prototype proves the local workflow and fixture adapters. It does not prove live provider credentials, production auth, tenant isolation, cloud storage, migrations, or deployment infrastructure. Treat those as deployment work, not as browser-demo evidence.
