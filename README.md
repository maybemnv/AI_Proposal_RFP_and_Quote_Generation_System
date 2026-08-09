# Proposal Workflow Prototype

This repository is a deterministic prototype for turning CRM/RFP source material into a source-linked proposal, a rule-backed quote, role-gated approvals, a rendered PDF, delivery, and post-send engagement analytics.

The default demo mode is fixture-backed. It needs no provider credentials and keeps the same contracts used by live generation and provider adapters.

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m app.cli reset
python -m app.cli demo
```

The demo prints the ten workflow gates and writes the rendered PDF below `var/storage/`.

To run the API and web shell:

```bash
uvicorn app.api.main:app --reload
cd app/web
npm install
npm run dev
```

Open `http://localhost:3000`. The API defaults to the `DATABASE_URL` in `.env`; copy `.env.example` first when using Docker Postgres. The standalone web prototype also has deterministic fixture fallbacks for portfolio screens.

## Verification

```bash
python -m pytest -q
ruff check app/
cd app/web
npm run build
npm run e2e
```

The browser suite covers capture, evidence, scope, pricing, approvals, preview/PDF download, content expiry, analytics, and the Trace A smoke path.

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

Fixture mode is intentionally the reliable demo path. Auth, tenant provisioning, migrations, live provider credentials, multi-currency, and production deployment are outside this prototype.
