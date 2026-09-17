# Plan 001: Make the fixture proposal showcase launchable, API-backed, and PDF-verifiable

> **Executor instructions**: Follow this plan in order. Use red-green-refactor: write one focused failing test, run it and confirm the expected failure, then write the smallest production change that makes it pass. Run every verification command before advancing. If a STOP condition occurs, stop and report; do not improvise. When a reviewer approves the completed work, update the row in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat f5088a0..HEAD -- app/api/main.py app/api/routes/documents.py app/adapters/storage.py app/web app/tests README.md docs/DEMO_RUNBOOK.md .env.example plans`
> If an in-scope file changed, compare the excerpts below to live code. A material mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: none
- **Category**: bug, tests, dx, docs
- **Planned at**: commit `f5088a0`, 2026-08-19

## Why this matters

The required showcase is a fixture-first browser story: import opportunity/RFP material, show evidence and deterministic pricing, lock approval, download the rendered PDF, and show engagement analytics. Today the browser makes successful-looking fallback state after API failures, while the PDF fallback is unrelated to the server-rendered document. This plan makes the actual fixture API, rendered artifact, health/readiness check, and browser tests agree without adding live provider requirements.

## Current state

- `app/api/main.py` creates the FastAPI app and CORS policy. Its relevant current shape is `allow_origins=["http://localhost:3000"]` at lines 12-18 and it registers only `/v1` routers at lines 19-24; it has no health/readiness route.
- `app/web/lib/api.ts:23-33` defaults to `http://localhost:8000` and parses every nonempty response with `JSON.parse`.
- `app/web/playwright.config.ts:8-17` starts only `npm run dev` on port 3000; therefore current E2E does not start/reset the API.
- `app/web/app/opportunities/page.tsx:26-43`, `proposals/[id]/scope/page.tsx:32-43`, `quote/page.tsx:37-54`, and `approval/page.tsx:36-45` replace API failures with locally successful fixture state. The desired convention is existing `ApiError`/`FlagList` presentation (`app/web/lib/api.ts:8-20`, `app/web/components/FlagList.tsx`).
- `app/adapters/storage.py:35-58` stores a rendered file locally and returns `target.as_uri()`; `app/api/routes/documents.py:80-99` returns that local URI. `preview/page.tsx:20-39` then creates a synthetic fallback blob. Do not expose arbitrary filesystem paths: retain `LocalStorage._resolve()` containment at `storage.py:47-52`.
- `app/adapters/documents.py:94-116` is the canonical renderer: Chromium writes the PDF. `app/tests/test_documents.py:80-83` is the existing Python test pattern for asserting a rendered PDF starts with `%PDF`.
- `README.md` and `docs/DEMO_RUNBOOK.md` are the existing user-facing launch and demo documentation. The product intent requires deterministic fixture mode, no paid credentials, a health/readiness check, a reset path, desktop and mobile browser smoke coverage, and an explicit fixture/live boundary.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Branch | `git switch -c feat/demo-showcase-ready` | branch created from reviewed base |
| Python install | `python -m pip install -e ".[dev]"` | exit 0 |
| Database | `docker compose up -d db` | database service running |
| Reset fixture data | `python -m app.cli reset` | reports seeded proposal versions |
| Backend tests | `python -m pytest -q` | all tests pass |
| Backend lint | `ruff check app/` | exit 0 |
| Web install | `cd app/web; npm ci` | exit 0 |
| Web build | `cd app/web; npm run build` | exit 0 |
| Browser install | `cd app/web; npx playwright install chromium` | Chromium available |
| Browser suite | `cd app/web; npm run e2e` | desktop and mobile tests pass |

Use the planned showcase ports in all new commands and config: API `8106`, web `3106`. The final docs must show a PowerShell-friendly two-terminal launch: `uvicorn app.api.main:app --port 8106` and, from `app/web`, `npm run dev` (the script itself must bind `3106`).

## Suggested executor toolkit

- Use `superpowers:test-driven-development` for every behavior change. Do not write production code before the focused test has failed for the intended reason.
- If dispatched through the subagent workflow, use one implementation task at a time, provide this plan as the authoritative brief, and require a scoped review after each commit checkpoint.

## Scope

**In scope** (only these paths may change):

- `app/api/main.py`, `app/api/routes/documents.py`, `app/adapters/storage.py`
- `app/tests/test_api.py`, `app/tests/test_documents.py`
- `app/web/package.json`, `app/web/lib/api.ts`, `app/web/playwright.config.ts`
- `app/web/app/opportunities/page.tsx`, `app/web/app/proposals/[id]/scope/page.tsx`, `app/web/app/proposals/[id]/quote/page.tsx`, `app/web/app/proposals/[id]/approval/page.tsx`, `app/web/app/proposals/[id]/preview/page.tsx`
- `app/web/e2e/trace-a.spec.ts`, `app/web/e2e/preview.spec.ts`, and a new focused mobile E2E spec under `app/web/e2e/`
- `README.md`, `docs/DEMO_RUNBOOK.md`, `.env.example`, `plans/README.md`

**Out of scope**:

- `debug.log` (untracked): do not touch it for any reason.
- `.claude/settings.local.json`: local ignored agent configuration; do not follow, edit, stage, or commit it.
- Live CRM/model/signature/delivery providers, auth, tenant isolation, migrations, object storage, and production hosting.
- Any change outside fixture/demo data or any use of credential values. Refer only to credential type and location if one is encountered, and stop for rotation guidance.

## Git workflow

- Branch: `feat/demo-showcase-ready`.
- Match the observed conventional style: `feat: ...`, `test: ...`, `docs: ...` (for example, `f5088a0` is `test: end-to-end traces proving I1-I10, plus the demo runbook`).
- Commit checkpoints: (1) readiness/download API plus Python tests, (2) API-backed web behavior plus Playwright tests, (3) documentation and final verification.
- Do not push, open a PR, or stage `debug.log` without separate operator authorization. If authorized later, push this branch and open one focused PR containing only the intended tracked files and the plan index update.

## Steps

### Step 1: Establish API fixture readiness and a safe PDF download contract (RED → GREEN → REFACTOR)

1. Add focused failing tests first in `app/tests/test_api.py` for a health/readiness response that distinguishes a running process from unseeded/unavailable fixture data, and in `app/tests/test_documents.py` for retrieving a rendered document by its document/version identifier. The test must assert PDF content begins with `%PDF`, not merely that a filename ends in `.pdf`.
2. Run only the new focused tests and confirm they fail because the endpoints/contract do not exist: `python -m pytest app/tests/test_api.py app/tests/test_documents.py -q`.
3. Implement the smallest health/readiness route in `app/api/main.py` and a bounded download route in `app/api/routes/documents.py`. The endpoint must resolve the existing stored document through the repository/storage contract, return `application/pdf`, and reject unknown IDs. It must never accept a caller-supplied filesystem path or return `file://` to the browser.
4. Adjust `app/adapters/storage.py` only if a narrow storage accessor is needed; preserve its existing root containment behavior.
5. Re-run the focused tests, then `python -m pytest -q` and `ruff check app/`.

**Verify**: focused tests first fail for the missing behavior, then pass; the full Python suite and Ruff exit 0.

### Step 2: Bind the web app to the fixture API instead of success-on-error fallbacks (RED → GREEN → REFACTOR)

1. Add/update one browser test in `app/web/e2e/trace-a.spec.ts` that proves each visible mutation has API-backed state: import result, scope resolution, recalculated quote, approval lock, and rendered document. Configure it to use API `8106` and web `3106` with clean fixture state.
2. Run the focused spec and confirm it fails against the current static fallback behavior.
3. Update `app/web/lib/api.ts`, `package.json`, and `playwright.config.ts` so default local fixture operation targets `http://localhost:8106`, Next runs on `3106`, and Playwright starts/resets both required services or stops with a clear prerequisite failure. Do not use hidden pre-existing browser/API processes as test state.
4. Update the five named pages to retain fixture content only as initial display data where appropriate, but never convert a rejected/unavailable mutation into successful workflow state. Use the existing `ApiError`/`FlagList` pattern and visible error state.
5. Update CORS/readiness configuration in `app/api/main.py` for the planned web origin only; do not broaden it to wildcards.
6. Re-run the focused browser test, then `npm run build` and `npm run e2e`.

**Verify**: intentionally stopping API `8106` produces a visible unavailable/error state rather than a completed action; with API running and reset, the trace completes from actual responses.

### Step 3: Verify the real rendered artifact and mobile smoke path (RED → GREEN → REFACTOR)

1. Change `app/web/e2e/preview.spec.ts` so the download assertion reads the saved artifact and verifies PDF signature/nontrivial output, not only `suggestedFilename()`.
2. Add a mobile project or focused mobile spec under `app/web/e2e/` at a narrow viewport. It must cover the primary Trace A route and ensure critical controls remain visible and operable.
3. Run the new/changed focused specs; record the expected RED failures before changing production code/config.
4. Make only the smallest layout/configuration changes needed for the tests. Do not introduce a second mock document or a separate demo-only workflow.
5. Run `cd app/web; npm run e2e` and retain Playwright artifacts only in ignored output directories.

**Verify**: browser suite downloads the server-rendered artifact, validates its bytes, and passes both desktop and mobile projects.

### Step 4: Publish a clean fixture launch/runbook after behavior is verified

1. Update `.env.example`, `README.md`, and `docs/DEMO_RUNBOOK.md` only after the preceding tests are green.
2. Document prerequisites, fixture-only variables without secret values, API `8106`, web `3106`, reset, readiness URL/expected response, browser/PDF verification, expected demo outcome, fixture/live boundary, and shutdown.
3. Use `npm ci`, never an undocumented mutable dependency installation, in the reproducible web path. Explain that live providers remain optional and unverified.
4. Run all commands exactly as documented from a clean shell where practical.

**Verify**: `python -m pytest -q`; `ruff check app/`; `cd app/web; npm ci; npm run build; npm run e2e`; `git diff --check`; `git status --short` shows only planned tracked changes plus pre-existing untracked `debug.log`.

## Test plan

- `app/tests/test_api.py`: health/readiness success and not-ready/error semantics using the existing API-client fixture pattern.
- `app/tests/test_documents.py`: rendered fixture artifact can be downloaded through the public document endpoint; unknown document is rejected; no path parameter is accepted.
- `app/web/e2e/trace-a.spec.ts`: actual API reset/startup and each workflow state transition.
- `app/web/e2e/preview.spec.ts`: downloaded content is a server-rendered PDF, not filename-only/fallback proof.
- New mobile E2E spec: primary scenario at narrow viewport with critical action visibility.

## Done criteria

- [ ] API `8106` and web `3106` are the only documented/default showcase ports for this repo.
- [ ] A health/readiness endpoint proves fixture data readiness without disclosing secrets.
- [ ] Browser mutations fail visibly when the API is unavailable; no action is locally marked complete after failed API response.
- [ ] Preview download is served through the API and test-verified as an actual PDF.
- [ ] `python -m pytest -q`, `ruff check app/`, `npm run build`, and `npm run e2e` all pass.
- [ ] Desktop and narrow mobile browser coverage covers the primary fixture story.
- [ ] Docs include prerequisites, startup, verification, reset, fixture/live boundary, and shutdown.
- [ ] No files outside Scope changed; `debug.log` remains untracked and untouched.
- [ ] `plans/README.md` is updated after approved review.

## STOP conditions

- The drift check shows a material change to any excerpted route, storage, or E2E contract.
- Making the document downloadable requires exposing arbitrary disk paths, bypassing `LocalStorage._resolve`, or weakening CORS.
- A real PDF cannot be rendered in the intended clean environment after browser installation; report the renderer/browser error rather than adding a synthetic PDF fallback.
- The planned ports conflict with the portfolio coordinator’s final map.
- Any step requires a live provider credential, actual tenant auth, a destructive non-fixture database operation, or an out-of-scope file.
- A focused test does not first fail for the intended missing behavior, or a verification fails twice after a reasonable minimal correction.

## Maintenance notes

- Future storage providers should implement the same identifier-based download contract; never teach UI code provider-specific filesystem URIs.
- Reviewers should verify each workflow mutation is derived from server response and that the E2E harness owns its data lifecycle.
- Live provider/auth work remains a separate production plan; fixture mode must stay credential-free.
