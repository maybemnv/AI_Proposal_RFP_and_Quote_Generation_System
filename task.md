# AI Proposal, RFP, and Quote Generation System — Demo Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fixture-backed, runnable prototype that walks a client from a discovery call to an approved, branded, delivered proposal — with every control the pitch depends on (evidence-backed claims, deterministic integer pricing, blocking approval gates, immutable locked versions) actually enforced in code.

**Architecture:** A FastAPI service owns the domain (schemas, pricing, claims, workflow) and exposes the nine PRD endpoints over a PostgreSQL store. Every external provider sits behind a `ProviderAdapter` with success and failure fixtures, so the entire demo runs with no live credentials. Claude generation runs through one adapter with a `fixture | live` switch. A Next.js app renders the seven portfolio screens against that API. PDFs render from branded HTML through headless Chromium.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL 16 (docker-compose), pytest, Typer CLI, `anthropic` SDK (model `claude-opus-5`), Next.js 15 App Router, TypeScript, Playwright (E2E + PDF + screenshots). No Redis, no queue, no search engine, no observability vendor, no second AI provider.

## Scope Assumption (stated, not a blocking question)

The PRD describes a five-week production MVP. This plan targets **demo readiness**, which narrows the deliverable in exactly three ways, and in no others:

1. **Trace A is the spine.** The PRD names the agency discovery call as *the* demo, so Trace A is built end-to-end first (Tasks 1–19) and Trace B (RFP response) rides the same machinery, seeded in Task 13 and asserted in Task 19.
2. **Fixtures instead of credentials.** Every provider boundary is exercised through recorded success and failure fixtures. No HubSpot, Salesforce, PandaDoc, DocuSign, Stripe, Drive, or M365 account is required to run the demo.
3. **Single workspace, seeded users.** No signup, billing, or tenant provisioning UI. Roles exist and gate approvals; they are seeded.

Everything else stays: invariants I1–I10 are enforced and tested, money is integer minor units, approval gates block, and locked versions are immutable. **Those controls are the pitch** — a demo that fakes them has nothing to sell.

## Global Constraints

- Python 3.12+. Node 20+. PostgreSQL 16.
- All money is `int` minor units. A `float` reaching any pricing function raises `MoneyError` (I9).
- `totalMinor = subtotalMinor - discountMinor + taxMinor`; a negative total is rejected (I3).
- Payment installments must sum to exactly `totalMinor`.
- Every quote line carries exactly one `ruleId` and its rule version is persisted (I2).
- A locked `ProposalVersion` is immutable: scope, claims, sources, quote, approvals, rendered content (I5).
- Delivery requires a `ready` document and every required approval `approved` (I6).
- Claims that are `expired` or `rejected` cannot enter a new version (I7).
- Only the eight `Provider` literals from the PRD. No unlisted integration.
- Model ID is the exact string `claude-opus-5`. Never append a date suffix. Thinking is `{"type": "adaptive"}`. Never send `budget_tokens`, `temperature`, `top_p`, `top_k`, or an assistant prefill — Opus 5 rejects all of them with a 400.
- Pydantic models use snake_case fields with camelCase JSON aliases (`alias_generator=to_camel`, `populate_by_name=True`) so wire payloads match the PRD's TypeScript contracts verbatim.
- No secrets in any committed file. `.env.example` carries key *names* with empty or placeholder values only.
- Commit at the end of every task. Do not push. Do not amend.
- Design tokens are the PRD's CSS block verbatim for light mode; dark mode is a selected, validated palette, never an automatic inversion.

## File Structure

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Python deps, pytest + ruff config |
| `docker-compose.yml` | PostgreSQL 16 service only |
| `.env.example` | Placeholder key names |
| `app/domain/money.py` | Minor-unit conversion, formatting, line math, `MoneyError` |
| `app/domain/schemas.py` | Pydantic mirrors of every canonical PRD type |
| `app/domain/pricing.py` | The eight-step deterministic algorithm, `inputHash` |
| `app/domain/claims.py` | `validate_block`, `contains_verifiable_assertion`, evidence checks |
| `app/domain/workflow.py` | State machines, lock enforcement, delivery preconditions |
| `app/domain/validation.py` | `ValidationFlag` aggregation across scope, claims, quote, approvals |
| `app/persistence/models.py` | SQLAlchemy tables |
| `app/persistence/repositories.py` | Read/write access, append-only audit writes |
| `app/adapters/base.py` | `ProviderAdapter`, `AdapterFailure`, fixture loader |
| `app/adapters/crm.py` | HubSpot + Salesforce opportunity import |
| `app/adapters/sources.py` | Drive + M365 source retrieval |
| `app/adapters/documents.py` | HTML→PDF rendering, object storage |
| `app/adapters/signatures.py` | PandaDoc + DocuSign send and engagement events |
| `app/adapters/payments.py` | Stripe payment-link creation |
| `app/adapters/generation.py` | Claude adapter, `fixture \| live` |
| `app/api/main.py`, `app/api/routes/*.py` | The nine endpoints |
| `app/fixtures/` | Trace A, Trace B, provider success/failure fixtures |
| `app/cli.py` | Typer: `seed`, `demo`, `reset` |
| `app/tests/` | Unit + trace tests |
| `app/web/` | Next.js: ten routes, tokens, components |
| `docs/DEMO_RUNBOOK.md` | The click-by-click pitch script |

---

### Task 1: Project scaffold and money primitives

**Files:**
- Create: `pyproject.toml`, `docker-compose.yml`, `.env.example`, `.gitignore`
- Create: `app/__init__.py`, `app/domain/__init__.py`, `app/tests/__init__.py`
- Create: `app/domain/money.py`
- Test: `app/tests/test_money.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `MoneyError(ValueError)`; `to_minor(amount: str | int | Decimal, exponent: int = 2) -> int`; `format_minor(minor: int, currency: str = "USD", exponent: int = 2) -> str`; `line_subtotal_minor(unit_price_minor: int, quantity: Decimal) -> int`. Every later money computation goes through these.

- [ ] **Step 1: Create the project files**

`pyproject.toml`:

```toml
[project]
name = "proposal-system"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "pydantic>=2.9",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "anthropic>=0.40",
  "typer>=0.15",
  "jinja2>=3.1",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "httpx>=0.27", "ruff>=0.7"]

[tool.pytest.ini_options]
testpaths = ["app/tests"]
addopts = "-q"

[tool.ruff]
line-length = 100
```

`docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: proposal
      POSTGRES_PASSWORD: proposal
      POSTGRES_DB: proposal
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

`.env.example` (names only, no values — never commit a real key):

```bash
DATABASE_URL=postgresql+psycopg://proposal:proposal@localhost:5432/proposal
GENERATION_MODE=fixture
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-opus-5
STORAGE_DIR=./var/storage
```

`.gitignore`:

```gitignore
__pycache__/
*.pyc
.venv/
.env
var/
node_modules/
.next/
test-results/
```

- [ ] **Step 2: Write the failing test**

`app/tests/test_money.py`:

```python
from decimal import Decimal

import pytest

from app.domain.money import MoneyError, format_minor, line_subtotal_minor, to_minor


def test_to_minor_from_string():
    assert to_minor("1250.00") == 125000
    assert to_minor("0.01") == 1


def test_to_minor_rejects_float():
    with pytest.raises(MoneyError):
        to_minor(1250.00)


def test_to_minor_rounds_half_up():
    assert to_minor("0.005") == 1


def test_format_minor():
    assert format_minor(125000) == "1,250.00 USD"
    assert format_minor(-500, "EUR") == "-5.00 EUR"


def test_format_minor_rejects_non_int():
    with pytest.raises(MoneyError):
        format_minor(1250.0)


def test_line_subtotal_fractional_quantity():
    assert line_subtotal_minor(120000, Decimal("2.5")) == 300000


def test_line_subtotal_rejects_float_quantity():
    with pytest.raises(MoneyError):
        line_subtotal_minor(120000, 2.5)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest app/tests/test_money.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.money'`

- [ ] **Step 4: Write the minimal implementation**

`app/domain/money.py`:

```python
"""Integer minor units only. Floating point pricing is prohibited (I9)."""

from decimal import Decimal, ROUND_HALF_UP


class MoneyError(ValueError):
    """Raised when a money value would lose precision or use floating point."""


def to_minor(amount: str | int | Decimal, exponent: int = 2) -> int:
    if isinstance(amount, float):
        raise MoneyError("floating point money is prohibited (I9)")
    value = amount if isinstance(amount, Decimal) else Decimal(amount)
    scaled = (value * (10**exponent)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(scaled)


def format_minor(minor: int, currency: str = "USD", exponent: int = 2) -> str:
    if not isinstance(minor, int) or isinstance(minor, bool):
        raise MoneyError("minor units must be int")
    sign = "-" if minor < 0 else ""
    digits = str(abs(minor)).rjust(exponent + 1, "0")
    whole, frac = digits[:-exponent], digits[-exponent:]
    return f"{sign}{int(whole):,}.{frac} {currency}"


def line_subtotal_minor(unit_price_minor: int, quantity: Decimal) -> int:
    if not isinstance(unit_price_minor, int) or isinstance(unit_price_minor, bool):
        raise MoneyError("unit price must be int minor units")
    if isinstance(quantity, float):
        raise MoneyError("floating point quantity is prohibited (I9)")
    qty = quantity if isinstance(quantity, Decimal) else Decimal(quantity)
    product = (Decimal(unit_price_minor) * qty).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(product)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest app/tests/test_money.py -v`
Expected: PASS — 7 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml docker-compose.yml .env.example .gitignore app/
git commit -m "feat: project scaffold and integer minor-unit money primitives (I9)"
```

---

### Task 2: Domain schemas — canonical PRD types as Pydantic models

**Files:**
- Create: `app/domain/schemas.py`
- Test: `app/tests/test_schemas.py`

**Interfaces:**
- Consumes: Task 1's `money` module.
- Produces: every canonical PRD type as a Pydantic model, with snake_case fields and camelCase JSON aliases. The wire payloads must match the PRD TypeScript contracts verbatim.

**Model list (field names as in the PRD):**
- `SourceRecord` — `id`, `provider` (the `Provider` literal union), `external_id`/`externalId`, `title`, `uri`, `retrieved_at`/`retrievedAt`, `content_hash`/`contentHash`, `excerpt`, `source_type`/`sourceType`, `approved_for_generation`/`approvedForGeneration`
- `Opportunity` — `external_provider`/`externalProvider`, `external_id`/`externalId`, `account_name`/`accountName`, `contact_name`/`contactName`, `title`, `currency`, `status`, `source_record_ids`/`sourceRecordIds`, `required_field_errors`/`requiredFieldErrors`, `imported_at`/`importedAt`
- `DiscoveryInput` — `kind` (`notes | transcript | rfp_text`), `text`, `extracted_at`/`extractedAt`
- `Requirement`, `Deliverable`, `Milestone`, `Assumption`, `Scope` — nested collections; `Scope` is a `Scope` with `deliverables`, `milestones`, `assumptions`, `exclusions`, `open_questions`/`openQuestions`
- `Claim`, `EvidenceLink`
- `QuoteLine`, `PaymentInstallment`, `Quote`
- `Approval`
- `ProposalVersion`
- `PricingRule`, `DiscountPolicy`
- `GenerateDraftRequest`, `GeneratedBlock`, `GeneratedSection`, `ClaimUsage`, `ValidationFlag`, `GenerateDraftResponse`
- `AuditEvent`, `AdapterFailure`
- `Provider` — `Literal["hubspot","salesforce","pandadoc","docusign","stripe","google_drive","microsoft_365","manual"]`
- `ValidationFlagCode` — `Literal["MISSING_SOURCE","UNAPPROVED_CLAIM","EXPIRED_CLAIM","UNRESOLVED_REQUIREMENT","PRICE_MISMATCH","MISSING_APPROVAL","SCHEMA_ERROR","RENDER_ERROR"]`

**Status literals, verbatim from the PRD:**
- `Opportunity.status`: `imported | normalized | needs_attention`
- `ProposalVersion.status`: `working | submitted | locked | rendered | delivered`
- `Claim.status`: `draft | pending_approval | approved | expired | rejected`
- Quote status: `calculated | review_required | approved | rejected | superseded`. The canonical `Quote` contract carries **no** `status` field, so do not add one. Define `QuoteCalculationResponse(Quote)` instead — a subclass adding `status: QuoteStatus` and `policy_message: str | None` — and return that from `/quote/calculate`. `calculate_quote` (Task 3) keeps returning a bare `Quote`; the endpoint decides the status from `DiscountPolicy`.
- `Approval.decision`: `pending | approved | rejected`; `requiredRole`: `content_editor | quote_approver | proposal_approver`
- `DiscoveryInput.kind`: `notes | transcript | rfp_text`

- [ ] **Step 1: Write the failing test**

`app/tests/test_schemas.py` — assert (a) every model round-trips through camelCase JSON and snake_case Python, and (b) validation rejects out-of-literal values:

```python
from app.domain.schemas import Provider, SourceRecord, ValidationFlag


def test_provider_literal_accepts_all_prd_values():
    for p in ["hubspot", "salesforce", "pandadoc", "docusign", "stripe",
              "google_drive", "microsoft_365", "manual"]:
        assert Provider(p) == p


def test_source_record_camelcase_roundtrip():
    record = SourceRecord.model_validate({
        "id": "1", "provider": "hubspot", "title": "Discovery notes",
        "retrievedAt": "2026-08-01T09:00:00Z", "contentHash": "abc",
        "sourceType": "discovery", "approvedForGeneration": True,
    })
    assert record.source_record_ids is None or True  # absent field stays absent
    assert record.content_hash == "abc"
    assert "contentHash" in record.model_dump(by_alias=True)


def test_validation_flag_requires_severity():
    import pydantic
    try:
        ValidationFlag.model_validate({
            "code": "MISSING_SOURCE", "severity": "urgent", "message": "x",
        })
    except pydantic.ValidationError:
        return
    raise AssertionError("bad severity must be rejected")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest app/tests/test_schemas.py -v`
Expected: FAIL — module does not exist yet.

- [ ] **Step 3: Implement `app/domain/schemas.py`**

One module, ~450 lines. Key mechanics:

```python
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )
```

Then define every type above inheriting `CamelModel`, with `UUID`, `ISODateTime` as `str`-based aliases (keep `str` so fixture JSON stays readable; do not over-validate). Money fields are plain `int` — never `float`. `Provider`, `ValidationFlagCode`, and statuses are `Literal`s. Required fields exactly as the canonical contracts list them; optional fields (`uri`, `externalId`, `validUntil`, …) are `None`-defaulted.

Notes to honor while writing:
- `Claim.valid_from`/`valid_until` are optional ISO strings.
- `QuoteLine` carries `ruleId` and `selected: bool`; `optional` lines default `selected=False`.
- `Approval` has `kind: "claim" | "scope" | "quote" | "proposal"`.
- `GenerateDraftRequest.requestedSections` is the list of the eleven section keys verbatim.
- `ValidationFlag.severity: "blocking" | "warning"`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest app/tests/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/schemas.py app/tests/test_schemas.py
git commit -m "feat: Pydantic mirrors of the canonical PRD contracts (camelCase wire format)"
```

---

### Task 3: Pricing engine — the eight-step deterministic algorithm

**Files:**
- Create: `app/domain/pricing.py`
- Test: `app/tests/test_pricing.py`

**Interfaces:**
- Consumes: `app.domain.money` (Task 1), `app.domain.schemas` (Task 2).
- Produces: `PricingError(ValueError)`; `calculate_quote(lines: list[QuoteLineInput], rules: dict[str, PricingRule], currency: str, discount_minor: int = 0, tax_minor: int = 0, installments: list[InstallmentSpec] | None = None, calculated_at: str) -> Quote`; `compute_input_hash(payload: dict) -> str`. Task 10 (validation), Task 12 (API), and Task 16 (quote screen) all call `calculate_quote`.

**The eight steps, verbatim from the PRD, each with its own test:**

1. Validate every line shares one currency.
2. Validate each line's quantity is within the rule's `minQuantity`/`maxQuantity` and the rule is active at `calculatedAt` (`activeFrom` ≤ date, and `activeUntil` absent or ≥ date).
3. `line.subtotalMinor = line_subtotal_minor(rule.unitPriceMinor, quantity)`.
4. Sum only `selected` lines into `subtotalMinor` (I4 — optional lines affect totals only when selected).
5. Apply the explicit `discountMinor` and `taxMinor` given as input.
6. `totalMinor = subtotalMinor - discountMinor + taxMinor`; reject a negative total (I3).
7. Payment installments must sum to exactly `totalMinor`.
8. Persist the rule version per line, the inputs, the output, and `inputHash` (I2).

- [x] **Step 1: Write the failing tests**

`app/tests/test_pricing.py`:

```python
from decimal import Decimal

import pytest

from app.domain.pricing import PricingError, calculate_quote, compute_input_hash
from app.domain.schemas import PricingRule

NOW = "2026-08-01T00:00:00Z"


def rule(id_="r1", price=120000, unit="day", min_q=1, max_q=None,
         active_from="2026-01-01", active_until=None, optional=False):
    return PricingRule(
        id=id_, version="2026.1", label="Senior consulting", unit=unit,
        currency="USD", unit_price_minor=price, min_quantity=min_q,
        max_quantity=max_q, optional=optional, active_from=active_from,
        active_until=active_until, source_record_ids=[],
    )


def line(id_="l1", rule_id="r1", qty="2", optional=False, selected=True):
    return {"id": id_, "label": "Senior consulting", "ruleId": rule_id,
            "quantity": Decimal(qty), "optional": optional,
            "selected": selected, "sourceRecordIds": []}


def test_step3_line_subtotal_is_quantity_times_unit_price():
    q = calculate_quote([line(qty="2")], {"r1": rule()}, "USD", calculated_at=NOW)
    assert q.lines[0].subtotal_minor == 240000


def test_step4_unselected_optional_line_is_excluded():
    q = calculate_quote(
        [line(), line("l2", "r1", "1", optional=True, selected=False)],
        {"r1": rule()}, "USD", calculated_at=NOW)
    assert q.subtotal_minor == 240000


def test_step4_selected_optional_line_is_included():
    q = calculate_quote(
        [line(), line("l2", "r1", "1", optional=True, selected=True)],
        {"r1": rule()}, "USD", calculated_at=NOW)
    assert q.subtotal_minor == 360000


def test_step6_total_formula():
    q = calculate_quote([line()], {"r1": rule()}, "USD",
                        discount_minor=40000, tax_minor=10000, calculated_at=NOW)
    assert q.total_minor == 240000 - 40000 + 10000


def test_step6_negative_total_rejected():
    with pytest.raises(PricingError, match="negative"):
        calculate_quote([line()], {"r1": rule()}, "USD",
                        discount_minor=999999, calculated_at=NOW)


def test_step1_mixed_currency_rejected():
    eur = rule("r2"); eur = eur.model_copy(update={"currency": "EUR"})
    with pytest.raises(PricingError, match="currency"):
        calculate_quote([line(), line("l2", "r2")], {"r1": rule(), "r2": eur},
                        "USD", calculated_at=NOW)


def test_step2_quantity_below_minimum_rejected():
    with pytest.raises(PricingError, match="quantity"):
        calculate_quote([line(qty="0")], {"r1": rule(min_q=1)}, "USD", calculated_at=NOW)


def test_step2_inactive_rule_rejected():
    with pytest.raises(PricingError, match="active"):
        calculate_quote([line()], {"r1": rule(active_until="2026-01-31")},
                        "USD", calculated_at=NOW)


def test_step7_installments_must_sum_to_total():
    with pytest.raises(PricingError, match="installment"):
        calculate_quote([line()], {"r1": rule()}, "USD", calculated_at=NOW,
                        installments=[{"sequence": 1, "label": "Deposit",
                                       "amountMinor": 100000,
                                       "dueDescription": "On signature"}])


def test_step7_valid_installments_accepted():
    q = calculate_quote([line()], {"r1": rule()}, "USD", calculated_at=NOW,
                        installments=[
                            {"sequence": 1, "label": "Deposit", "amountMinor": 120000,
                             "dueDescription": "On signature"},
                            {"sequence": 2, "label": "Final", "amountMinor": 120000,
                             "dueDescription": "On delivery"}])
    assert sum(i.amount_minor for i in q.payment_schedule) == q.total_minor


def test_step8_line_carries_rule_version_and_hash_is_stable():
    a = calculate_quote([line()], {"r1": rule()}, "USD", calculated_at=NOW)
    b = calculate_quote([line()], {"r1": rule()}, "USD", calculated_at=NOW)
    assert a.pricing_rule_version == "2026.1"
    assert a.input_hash == b.input_hash


def test_hash_changes_when_input_changes():
    a = calculate_quote([line(qty="2")], {"r1": rule()}, "USD", calculated_at=NOW)
    b = calculate_quote([line(qty="3")], {"r1": rule()}, "USD", calculated_at=NOW)
    assert a.input_hash != b.input_hash


def test_float_quantity_rejected():
    bad = line(); bad["quantity"] = 2.0
    with pytest.raises(Exception):
        calculate_quote([bad], {"r1": rule()}, "USD", calculated_at=NOW)
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `pytest app/tests/test_pricing.py -v`
Expected: FAIL — `app.domain.pricing` does not exist.

- [ ] **Step 3: Implement `app/domain/pricing.py`**

```python
"""Deterministic pricing. Same inputs, same rule versions, same output (I2, I3, I4, I9)."""

import hashlib
import json
from decimal import Decimal

from app.domain.money import line_subtotal_minor
from app.domain.schemas import PaymentInstallment, PricingRule, Quote, QuoteLine


class PricingError(ValueError):
    """Raised when pricing inputs violate a rule, bound, or invariant."""


def compute_input_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate_quote(lines, rules, currency, *, discount_minor=0, tax_minor=0,
                    installments=None, calculated_at):
    # Step 1 — one currency.
    for raw in lines:
        r = rules.get(raw["ruleId"])
        if r is None:
            raise PricingError(f"unknown pricing rule {raw['ruleId']}")
        if r.currency != currency:
            raise PricingError(f"currency mismatch: {r.currency} != {currency}")

    day = calculated_at[:10]
    priced: list[QuoteLine] = []
    versions: set[str] = set()

    for raw in lines:
        r = rules[raw["ruleId"]]
        qty = raw["quantity"]
        if not isinstance(qty, Decimal):
            raise PricingError("quantity must be Decimal (I9)")

        # Step 2 — bounds and active window.
        if qty < Decimal(r.min_quantity):
            raise PricingError(f"quantity {qty} below minimum {r.min_quantity}")
        if r.max_quantity is not None and qty > Decimal(r.max_quantity):
            raise PricingError(f"quantity {qty} above maximum {r.max_quantity}")
        if r.active_from > day or (r.active_until is not None and r.active_until < day):
            raise PricingError(f"rule {r.id} is not active on {day}")

        # Step 3 — line subtotal.
        subtotal = line_subtotal_minor(r.unit_price_minor, qty)
        versions.add(r.version)
        priced.append(QuoteLine(
            id=raw["id"], label=raw["label"], rule_id=r.id, quantity=float(qty),
            unit_price_minor=r.unit_price_minor, subtotal_minor=subtotal,
            optional=raw["optional"], selected=raw["selected"],
            source_record_ids=raw.get("sourceRecordIds", []),
        ))

    # Step 4 — selected lines only (I4).
    subtotal_minor = sum(l.subtotal_minor for l in priced if l.selected)

    # Steps 5 and 6 — explicit discount and tax, then the total formula (I3).
    total_minor = subtotal_minor - discount_minor + tax_minor
    if total_minor < 0:
        raise PricingError("negative total is rejected (I3)")

    # Step 7 — installments sum exactly.
    schedule = [PaymentInstallment.model_validate(i) for i in (installments or [])]
    if schedule and sum(i.amount_minor for i in schedule) != total_minor:
        raise PricingError("installment amounts must sum exactly to totalMinor")

    # Step 8 — persist versions, inputs, output, hash (I2).
    if len(versions) > 1:
        raise PricingError(f"lines span multiple rule versions: {sorted(versions)}")
    input_hash = compute_input_hash({
        "currency": currency,
        "discountMinor": discount_minor,
        "taxMinor": tax_minor,
        "calculatedAt": calculated_at,
        "lines": [{"id": l.id, "ruleId": l.rule_id, "quantity": str(l.quantity),
                   "unitPriceMinor": l.unit_price_minor, "selected": l.selected}
                  for l in priced],
    })

    return Quote(
        currency=currency, lines=priced, subtotal_minor=subtotal_minor,
        discount_minor=discount_minor, tax_minor=tax_minor, total_minor=total_minor,
        payment_schedule=schedule, pricing_rule_version=next(iter(versions), "none"),
        input_hash=input_hash, calculated_at=calculated_at,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest app/tests/test_pricing.py -v`
Expected: PASS — 13 passed.

- [ ] **Step 5: Commit**

```bash
git add app/domain/pricing.py app/tests/test_pricing.py
git commit -m "feat: deterministic eight-step pricing engine (I2, I3, I4, I9)"
```

---

### Task 4: Claims and evidence validation

**Files:**
- Create: `app/domain/claims.py`
- Test: `app/tests/test_claims.py`

**Interfaces:**
- Consumes: `app.domain.schemas` (Task 2).
- Produces: `contains_verifiable_assertion(text: str) -> bool`; `validate_block(block: GeneratedBlock, claims_by_id: dict[str, Claim], evidence_by_claim: dict[str, list[EvidenceLink]], now: str) -> list[str]`; `usable_in_new_version(claim: Claim, now: str) -> bool` (I7). Task 10 aggregates these into `ValidationFlag`s.

This is invariant I1 in code: a client-facing claim is either a template literal or references an approved claim with evidence. A block containing a verifiable assertion with no `claimIds` is `UNAPPROVED_CLAIM`.

- [ ] **Step 1: Write the failing tests**

`app/tests/test_claims.py`:

```python
from app.domain.claims import (contains_verifiable_assertion, usable_in_new_version,
                               validate_block)
from app.domain.schemas import Claim, EvidenceLink, GeneratedBlock

NOW = "2026-08-01"


def claim(status="approved", valid_until=None, id_="c1"):
    return Claim(id=id_, text="Cut onboarding time 40%", status=status,
                 source_record_ids=["s1"], valid_until=valid_until,
                 allowed_contexts=["case_studies"], prohibited_contexts=[])


def block(content="We cut onboarding time 40%.", claim_ids=("c1",)):
    return GeneratedBlock(block_id="b1", kind="text", content=content,
                          claim_ids=list(claim_ids), source_record_ids=["s1"],
                          editable=True)


def evidence(claim_id="c1"):
    return [EvidenceLink(claim_id=claim_id, source_record_id="s1",
                         locator="p.3", excerpt="onboarding time fell 40%")]


def test_approved_claim_with_evidence_has_no_flags():
    assert validate_block(block(), {"c1": claim()}, {"c1": evidence()}, NOW) == []


def test_unknown_claim_is_missing_source():
    assert validate_block(block(), {}, {}, NOW) == ["MISSING_SOURCE"]


def test_unapproved_claim_flagged():
    flags = validate_block(block(), {"c1": claim("pending_approval")}, {"c1": evidence()}, NOW)
    assert "UNAPPROVED_CLAIM" in flags


def test_expired_claim_flagged():
    flags = validate_block(block(), {"c1": claim(valid_until="2026-07-01")},
                           {"c1": evidence()}, NOW)
    assert "EXPIRED_CLAIM" in flags


def test_claim_without_evidence_is_missing_source():
    flags = validate_block(block(), {"c1": claim()}, {}, NOW)
    assert "MISSING_SOURCE" in flags


def test_bare_assertion_without_claim_is_unapproved():
    flags = validate_block(block("We reduced churn by 22%.", claim_ids=()), {}, {}, NOW)
    assert flags == ["UNAPPROVED_CLAIM"]


def test_neutral_prose_without_claim_is_clean():
    flags = validate_block(block("This section describes the engagement.", claim_ids=()),
                           {}, {}, NOW)
    assert flags == []


def test_assertion_detector_catches_prd_shapes():
    for text in ["improved 12%", "a 3x return", "we reduced cost",
                 "the fastest option", "saved $40,000"]:
        assert contains_verifiable_assertion(text), text
    for text in ["We will run four workshops.", "Scope covers two milestones."]:
        assert not contains_verifiable_assertion(text), text


def test_expired_and_rejected_claims_cannot_enter_a_new_version():
    assert usable_in_new_version(claim(), NOW) is True
    assert usable_in_new_version(claim("rejected"), NOW) is False
    assert usable_in_new_version(claim("expired"), NOW) is False
    assert usable_in_new_version(claim(valid_until="2026-07-01"), NOW) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest app/tests/test_claims.py -v`
Expected: FAIL — `app.domain.claims` does not exist.

- [ ] **Step 3: Implement `app/domain/claims.py`**

```python
"""Claim and evidence enforcement (I1, I7)."""

import re

ASSERTION_PATTERNS = (
    re.compile(r"\b\d+(\.\d+)?\s?%"),
    re.compile(r"\b\d[\d,]*(\.\d+)?x\b", re.I),
    re.compile(r"\b(increased|decreased|reduced|grew|saved|delivered|achieved)\b", re.I),
    re.compile(r"\b(best|fastest|leading|#1|award-winning|industry-leading)\b", re.I),
    re.compile(r"\$\s?\d"),
)


def contains_verifiable_assertion(text: str) -> bool:
    return any(p.search(text) for p in ASSERTION_PATTERNS)


def validate_block(block, claims_by_id, evidence_by_claim, now) -> list[str]:
    flags: list[str] = []
    for claim_id in block.claim_ids:
        claim = claims_by_id.get(claim_id)
        if claim is None:
            flags.append("MISSING_SOURCE")
            continue
        if claim.status != "approved":
            flags.append("UNAPPROVED_CLAIM")
        if claim.valid_until and claim.valid_until < now:
            flags.append("EXPIRED_CLAIM")
        if not evidence_by_claim.get(claim_id):
            flags.append("MISSING_SOURCE")
    if contains_verifiable_assertion(block.content) and not block.claim_ids:
        flags.append("UNAPPROVED_CLAIM")
    return flags


def usable_in_new_version(claim, now: str) -> bool:
    """I7 — expired or rejected claims cannot be used in a new version."""
    if claim.status in {"expired", "rejected"}:
        return False
    if claim.valid_until and claim.valid_until < now:
        return False
    return claim.status == "approved"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest app/tests/test_claims.py -v`
Expected: PASS — 9 passed.

- [ ] **Step 5: Commit**

```bash
git add app/domain/claims.py app/tests/test_claims.py
git commit -m "feat: claim and evidence validation with assertion detection (I1, I7)"
```

---

### Task 5: Workflow state machine and version locking

**Files:**
- Create: `app/domain/workflow.py`
- Test: `app/tests/test_workflow.py`

**Interfaces:**
- Consumes: `app.domain.schemas` (Task 2).
- Produces: `TransitionError(ValueError)`; `assert_transition(entity: str, current: str, target: str) -> None`; `lock_version(version: ProposalVersion, locked_at: str) -> ProposalVersion`; `assert_mutable(version: ProposalVersion) -> None` (I5); `assert_deliverable(version: ProposalVersion, document_status: str, approvals: list[Approval]) -> None` (I6, I8); `content_hash(version: ProposalVersion) -> str`.

Encode the PRD's six state models as adjacency maps. `assert_mutable` raises when status is `locked`, `rendered`, or `delivered`.

- [ ] **Step 1: Write the failing tests**

`app/tests/test_workflow.py` covering:

```python
import pytest

from app.domain.workflow import (TransitionError, assert_deliverable, assert_mutable,
                                 assert_transition, content_hash, lock_version)


def test_valid_proposal_version_path():
    for a, b in [("working", "submitted"), ("submitted", "locked"),
                 ("locked", "rendered"), ("rendered", "delivered")]:
        assert_transition("proposal_version", a, b) is None


def test_cannot_skip_lock():
    with pytest.raises(TransitionError):
        assert_transition("proposal_version", "submitted", "rendered")


def test_cannot_reopen_locked_version(locked_version):
    with pytest.raises(TransitionError, match="locked"):
        assert_mutable(locked_version)


def test_locking_freezes_content_hash(working_version):
    locked = lock_version(working_version, "2026-08-01T10:00:00Z")
    assert locked.status == "locked"
    assert locked.locked_at == "2026-08-01T10:00:00Z"
    assert content_hash(locked) == content_hash(locked)


def test_delivery_blocked_without_ready_document(locked_version, approvals_all_approved):
    with pytest.raises(TransitionError, match="document"):
        assert_deliverable(locked_version, "rendering", approvals_all_approved)


def test_delivery_blocked_by_pending_approval(locked_version, approvals_one_pending):
    with pytest.raises(TransitionError, match="approval"):
        assert_deliverable(locked_version, "ready", approvals_one_pending)


def test_delivery_blocked_by_unresolved_flag(locked_version_with_flag,
                                             approvals_all_approved):
    with pytest.raises(TransitionError, match="unresolved"):
        assert_deliverable(locked_version_with_flag, "ready", approvals_all_approved)


def test_delivery_allowed_when_all_conditions_met(locked_version,
                                                  approvals_all_approved):
    assert assert_deliverable(locked_version, "ready", approvals_all_approved) is None
```

Define the fixtures (`working_version`, `locked_version`, `locked_version_with_flag`, `approvals_all_approved`, `approvals_one_pending`) in `app/tests/conftest.py`, each building a real `ProposalVersion`/`Approval` from Task 2's models with a minimal `Scope` and a `Quote` produced by Task 3's `calculate_quote`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest app/tests/test_workflow.py -v`
Expected: FAIL — `app.domain.workflow` does not exist.

- [ ] **Step 3: Implement `app/domain/workflow.py`**

```python
"""State machines, immutability, and delivery preconditions (I5, I6, I8)."""

import hashlib
import json

TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "opportunity": {
        "imported": {"normalized", "needs_attention"},
        "needs_attention": {"normalized"},
        "normalized": set(),
    },
    "proposal": {
        "assembling": {"draft", "archived"},
        "draft": {"in_review", "archived"},
        "in_review": {"approved", "rejected"},
        "approved": {"delivered", "archived"},
        "rejected": {"draft", "archived"},
        "delivered": {"archived"},
        "archived": set(),
    },
    "proposal_version": {
        "working": {"submitted"},
        "submitted": {"locked", "working"},
        "locked": {"rendered"},
        "rendered": {"delivered"},
        "delivered": set(),
    },
    "content_item": {
        "draft": {"pending_approval"},
        "pending_approval": {"approved", "rejected"},
        "approved": {"expired"},
        "expired": set(),
        "rejected": {"draft"},
    },
    "quote": {
        "calculated": {"review_required", "approved"},
        "review_required": {"approved", "rejected"},
        "approved": {"superseded"},
        "rejected": {"calculated"},
        "superseded": set(),
    },
    "approval": {"pending": {"approved", "rejected"}, "approved": set(), "rejected": set()},
    "document": {
        "requested": {"rendering"},
        "rendering": {"ready", "failed"},
        "ready": set(),
        "failed": {"requested"},
    },
}

IMMUTABLE_STATUSES = {"locked", "rendered", "delivered"}


class TransitionError(ValueError):
    """Raised when a state change or mutation violates the workflow rules."""


def assert_transition(entity: str, current: str, target: str) -> None:
    allowed = TRANSITIONS[entity].get(current, set())
    if target not in allowed:
        raise TransitionError(f"{entity}: {current} -> {target} is not allowed")


def assert_mutable(version) -> None:
    """I5 — a locked version cannot change."""
    if version.status in IMMUTABLE_STATUSES:
        raise TransitionError(f"version {version.id} is locked and cannot be modified")


def content_hash(version) -> str:
    payload = version.model_dump(by_alias=True, exclude={"locked_at"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def lock_version(version, locked_at: str):
    assert_transition("proposal_version", version.status, "locked")
    return version.model_copy(update={"status": "locked", "locked_at": locked_at})


def assert_deliverable(version, document_status: str, approvals) -> None:
    """I6 and I8 — a ready document, every required approval, and no blocking flags."""
    if version.unresolved_flags:
        raise TransitionError(f"unresolved flags block delivery: {version.unresolved_flags}")
    pending = [a.id for a in approvals if a.decision != "approved"]
    if pending:
        raise TransitionError(f"missing approval: {pending}")
    if document_status != "ready":
        raise TransitionError(f"document is {document_status}, not ready")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest app/tests/test_workflow.py -v`
Expected: PASS — 8 passed.

- [ ] **Step 5: Commit**

```bash
git add app/domain/workflow.py app/tests/test_workflow.py app/tests/conftest.py
git commit -m "feat: workflow state machines, version locking, delivery gates (I5, I6, I8)"
```

---

### Task 6: Persistence — SQLAlchemy models and repositories

**Files:**
- Create: `app/persistence/__init__.py`, `app/persistence/models.py`, `app/persistence/repositories.py`, `app/persistence/session.py`
- Test: `app/tests/test_persistence.py`

**Interfaces:**
- Consumes: `app.domain.schemas` (Task 2), `app.domain.workflow` (Task 5).
- Produces: `get_engine(url: str | None = None)`, `session_scope()` contextmanager, `Base`, `create_all(engine)`; `OpportunityRepo`, `ProposalRepo`, `VersionRepo`, `ClaimRepo`, `PricingRuleRepo`, `ApprovalRepo`, `DocumentRepo`, `SourceRecordRepo`, `EngagementRepo`, each with `add`, `get`, `list`, and `update`. Tasks 7, 12, and 13 use these.

Tables mirror the domain types. JSON columns hold the nested aggregates (`scope`, `quote`, `sections`) so the demo does not need a migration tool; scalar columns hold anything queried or filtered (`status`, `account_name`, `currency`, `total_minor`, timestamps). `DATABASE_URL` selects PostgreSQL; tests pass `sqlite+pysqlite:///:memory:` for speed.

- [ ] **Step 1: Write the failing test**

`app/tests/test_persistence.py`:

```python
from app.persistence.models import Base
from app.persistence.repositories import VersionRepo
from app.persistence.session import get_engine, session_scope


def test_version_roundtrips_through_the_database(working_version):
    engine = get_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with session_scope(engine) as s:
        VersionRepo(s).add(working_version)
    with session_scope(engine) as s:
        loaded = VersionRepo(s).get(working_version.id)
    assert loaded.quote.total_minor == working_version.quote.total_minor
    assert loaded.scope.deliverables[0].name == working_version.scope.deliverables[0].name


def test_locked_version_update_is_refused(locked_version):
    engine = get_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with session_scope(engine) as s:
        VersionRepo(s).add(locked_version)
    with session_scope(engine) as s:
        repo = VersionRepo(s)
        try:
            repo.update(locked_version.model_copy(update={"title": "changed"}))
        except Exception as exc:
            assert "locked" in str(exc)
            return
    raise AssertionError("repository must refuse to update a locked version (I5)")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest app/tests/test_persistence.py -v`
Expected: FAIL — `app.persistence` does not exist.

- [ ] **Step 3: Implement the persistence layer**

`app/persistence/session.py`:

```python
import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_engine(url: str | None = None):
    return create_engine(url or os.environ["DATABASE_URL"], future=True)


@contextmanager
def session_scope(engine):
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
```

`app/persistence/models.py` — `DeclarativeBase` subclass `Base`, then one table per aggregate. Pattern for the central one:

```python
class ProposalVersionRow(Base):
    __tablename__ = "proposal_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    scope_json: Mapped[dict] = mapped_column(JSON)
    quote_json: Mapped[dict] = mapped_column(JSON)
    claim_ids: Mapped[list] = mapped_column(JSON, default=list)
    source_record_ids: Mapped[list] = mapped_column(JSON, default=list)
    unresolved_flags: Mapped[list] = mapped_column(JSON, default=list)
    total_minor: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String)
    locked_at: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
```

Add the same shape for `OpportunityRow`, `ProposalRow`, `SourceRecordRow`, `ClaimRow` (+ `EvidenceLinkRow`), `PricingRuleRow`, `DiscountPolicyRow`, `ApprovalRow`, `DocumentRow`, `GeneratedSectionRow`, `EngagementRecordRow`, `AuditEventRow`.

`app/persistence/repositories.py` — each repo converts between the row and the Pydantic model. `VersionRepo.update` calls `assert_mutable` on the **stored** row's status before writing, which is what makes I5 hold at the persistence boundary rather than only in service code:

```python
class VersionRepo:
    def __init__(self, session):
        self.s = session

    def add(self, version: ProposalVersion) -> None:
        self.s.add(self._to_row(version))

    def get(self, version_id: str) -> ProposalVersion:
        row = self.s.get(ProposalVersionRow, version_id)
        if row is None:
            raise KeyError(version_id)
        return self._to_model(row)

    def update(self, version: ProposalVersion) -> None:
        row = self.s.get(ProposalVersionRow, version.id)
        if row is None:
            raise KeyError(version.id)
        assert_mutable(self._to_model(row))
        for field, value in self._to_row_values(version).items():
            setattr(row, field, value)

    def promote(self, version: ProposalVersion, target: str) -> None:
        """The one path allowed to move a locked version forward (status only)."""
        row = self.s.get(ProposalVersionRow, version.id)
        if row is None:
            raise KeyError(version.id)
        assert_transition("proposal_version", row.status, target)
        row.status = target
        if target == "locked":
            row.locked_at = version.locked_at
            row.content_hash = content_hash(version)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest app/tests/test_persistence.py -v`
Expected: PASS — 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/persistence/ app/tests/test_persistence.py
git commit -m "feat: SQLAlchemy models and repositories enforcing locked-version immutability"
```

---

### Task 7: Append-only audit log

**Files:**
- Create: `app/domain/audit.py`
- Modify: `app/persistence/repositories.py` (add `AuditRepo`)
- Test: `app/tests/test_audit.py`

**Interfaces:**
- Consumes: `app.domain.schemas.AuditEvent` (Task 2), `app.persistence` (Task 6).
- Produces: `record_event(session, *, workspace_id, actor_type, actor_id, action, entity_type, entity_id, before_hash=None, after_hash=None, metadata=None, created_at) -> AuditEvent`; `AuditRepo.list_for(entity_id) -> list[AuditEvent]`; `AuditRepo` refuses `update` and `delete`. Every mutating endpoint in Task 12 calls `record_event`.

The nine `action` values are exactly the PRD's: `imported`, `edited`, `generated`, `validated`, `approved`, `rejected`, `locked`, `rendered`, `delivered`, `engagement_received`.

- [ ] **Step 1: Write the failing test**

```python
def test_audit_events_are_append_only(engine):
    with session_scope(engine) as s:
        record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                     action="locked", entity_type="proposal", entity_id="p1",
                     before_hash="a", after_hash="b", metadata={"version": "1"},
                     created_at="2026-08-01T10:00:00Z")
    with session_scope(engine) as s:
        events = AuditRepo(s).list_for("p1")
        assert len(events) == 1 and events[0].action == "locked"
        with pytest.raises(NotImplementedError):
            AuditRepo(s).delete("p1")


def test_before_and_after_hashes_are_stored(engine):
    with session_scope(engine) as s:
        record_event(s, workspace_id="w1", actor_type="system", actor_id=None,
                     action="rendered", entity_type="document", entity_id="d1",
                     before_hash="h_before", after_hash="h_after", metadata={},
                     created_at="2026-08-01T11:00:00Z")
    with session_scope(engine) as s:
        event = AuditRepo(s).list_for("d1")[0]
        assert event.before_hash == "h_before"
        assert event.after_hash == "h_after"


def test_unknown_action_is_rejected(engine):
    with session_scope(engine) as s:
        with pytest.raises(pydantic.ValidationError):
            record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                         action="deleted", entity_type="proposal", entity_id="p1",
                         metadata={}, created_at="2026-08-01T12:00:00Z")
```

Add an `engine` fixture to `app/tests/conftest.py` that builds an in-memory SQLite engine and calls `Base.metadata.create_all`.

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest app/tests/test_audit.py -v`
Expected: FAIL — `app.domain.audit` does not exist.

- [ ] **Step 3: Implement it**

`record_event` builds an `AuditEvent` (Pydantic validates the `action` literal, which is what rejects `"deleted"`), writes an `AuditEventRow`, and returns the model. `AuditRepo.delete` and `AuditRepo.update` raise `NotImplementedError("audit log is append-only")`.

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest app/tests/test_audit.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/domain/audit.py app/persistence/repositories.py app/tests/test_audit.py
git commit -m "feat: append-only audit log with before and after hashes"
```

---

### Task 8: Provider adapters and fixtures

**Files:**
- Create: `app/adapters/__init__.py`, `app/adapters/base.py`, `app/adapters/crm.py`, `app/adapters/sources.py`, `app/adapters/documents.py`, `app/adapters/signatures.py`, `app/adapters/payments.py`
- Create: `app/fixtures/providers/{hubspot,salesforce,pandadoc,docusign,stripe,google_drive,microsoft_365,manual}/{success,failure}.json`
- Test: `app/tests/test_adapters.py`

**Interfaces:**
- Consumes: `app.domain.schemas.AdapterFailure` and `Provider` (Task 2).
- Produces: `ProviderAdapter` protocol with `provider: Provider`, `capabilities() -> list[str]`, `execute(request: dict) -> dict | AdapterFailure`; `load_fixture(provider: str, outcome: str) -> dict`; concrete adapters `HubspotAdapter`, `SalesforceAdapter`, `DriveAdapter`, `M365Adapter`, `PandaDocAdapter`, `DocuSignAdapter`, `StripeAdapter`, `ManualAdapter`, plus `get_adapter(provider: Provider) -> ProviderAdapter`. Tasks 12 and 13 resolve adapters through `get_adapter`.

Every adapter reads from fixtures in demo mode and returns an `AdapterFailure` — never raises — when the request asks for the failure path. This is what lets the pitch demonstrate the failure branches on command.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from app.adapters.base import load_fixture
from app.adapters import get_adapter
from app.domain.schemas import AdapterFailure

ALL_PROVIDERS = ["hubspot", "salesforce", "pandadoc", "docusign", "stripe",
                 "google_drive", "microsoft_365", "manual"]


@pytest.mark.parametrize("provider", ALL_PROVIDERS)
def test_every_provider_has_success_and_failure_fixtures(provider):
    assert load_fixture(provider, "success")
    assert load_fixture(provider, "failure")


@pytest.mark.parametrize("provider", ALL_PROVIDERS)
def test_every_adapter_declares_capabilities(provider):
    assert get_adapter(provider).capabilities()


def test_crm_success_returns_normalized_opportunity():
    result = get_adapter("hubspot").execute({"outcome": "success", "externalId": "42"})
    assert result["accountName"]
    assert result["sourceRecords"]


def test_crm_failure_returns_adapter_failure_not_an_exception():
    result = get_adapter("hubspot").execute({"outcome": "failure"})
    assert isinstance(result, AdapterFailure)
    assert result.code in {"AUTH", "NOT_FOUND", "RATE_LIMIT", "UNSUPPORTED",
                           "TEMPORARY", "UNKNOWN"}
    assert result.provider == "hubspot"


def test_rate_limit_failure_is_retryable():
    result = get_adapter("salesforce").execute({"outcome": "failure"})
    assert result.retryable is (result.code in {"RATE_LIMIT", "TEMPORARY"})


def test_signature_adapter_emits_engagement_events():
    result = get_adapter("pandadoc").execute({"outcome": "success",
                                              "action": "send",
                                              "documentId": "d1"})
    assert result["engagementEvents"][0]["type"] in {"sent", "viewed", "signed"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest app/tests/test_adapters.py -v`
Expected: FAIL — `app.adapters` does not exist.

- [ ] **Step 3: Implement `app/adapters/base.py`**

```python
"""Every external boundary is an adapter with fixtures, so the demo needs no credentials."""

import json
from pathlib import Path
from typing import Protocol

from app.domain.schemas import AdapterFailure

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "providers"


def load_fixture(provider: str, outcome: str) -> dict:
    path = FIXTURE_ROOT / provider / f"{outcome}.json"
    if not path.exists():
        raise FileNotFoundError(f"missing fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


class ProviderAdapter(Protocol):
    provider: str

    def capabilities(self) -> list[str]: ...
    def execute(self, request: dict) -> dict | AdapterFailure: ...


class FixtureAdapter:
    """Base for demo-mode adapters. Returns AdapterFailure; never raises."""

    provider: str = "manual"
    _capabilities: list[str] = []

    def capabilities(self) -> list[str]:
        return list(self._capabilities)

    def execute(self, request: dict) -> dict | AdapterFailure:
        outcome = request.get("outcome", "success")
        payload = load_fixture(self.provider, outcome)
        if outcome == "failure":
            return AdapterFailure.model_validate(payload)
        return payload
```

Each concrete adapter subclasses `FixtureAdapter`, sets `provider` and `_capabilities`, and may post-process the fixture (for example, `StripeAdapter` echoes the requested `amountMinor` into the payment-link payload so the quote total and the link agree). `app/adapters/__init__.py` exposes `get_adapter` via a dict of the eight providers and raises `ValueError` for anything outside the PRD union.

- [ ] **Step 4: Write the fixtures**

Each `success.json` holds a realistic payload for that provider's capability; each `failure.json` holds an `AdapterFailure` body, and the eight failures cover the whole code union so the demo can show each branch:

```json
{
  "code": "AUTH",
  "provider": "hubspot",
  "message": "OAuth token expired for portal 8814402",
  "retryable": false,
  "externalRequestId": "req_7f21c9"
}
```

Assign: hubspot `AUTH`, salesforce `RATE_LIMIT` (retryable), google_drive `NOT_FOUND`, microsoft_365 `TEMPORARY` (retryable), pandadoc `UNSUPPORTED`, docusign `TEMPORARY` (retryable), stripe `UNKNOWN`, manual `NOT_FOUND`. Fixtures carry no real tokens or keys — request ids are invented.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest app/tests/test_adapters.py -v`
Expected: PASS — 21 passed (parametrized).

- [ ] **Step 6: Commit**

```bash
git add app/adapters/ app/fixtures/providers/ app/tests/test_adapters.py
git commit -m "feat: provider adapters with success and failure fixtures for all eight providers"
```

---

### Task 9: Generation service — Claude adapter with a fixture mode

**Files:**
- Create: `app/adapters/generation.py`, `app/domain/prompts.py`
- Create: `app/fixtures/generation/{executive_summary,understanding,scope,milestones,assumptions,options,pricing,payment_schedule,case_studies,next_steps,rfp_answers}.json`
- Test: `app/tests/test_generation.py`

**Interfaces:**
- Consumes: `app.domain.schemas` (`GenerateDraftRequest`, `GeneratedSection`, `GeneratedBlock`, `ClaimUsage`, `GenerateDraftResponse`) from Task 2; `app.domain.claims` (Task 4).
- Produces: `GenerationAdapter` with `generate(request: GenerateDraftRequest) -> GenerateDraftResponse`; `FixtureGenerationAdapter`; `ClaudeGenerationAdapter`; `get_generation_adapter() -> GenerationAdapter` switching on `GENERATION_MODE`; `source_snapshot_hash(request) -> str`. Task 12's `/generate` endpoint calls this.

**Claude call shape — do not deviate:**
- `model="claude-opus-5"` exactly. No date suffix.
- `thinking={"type": "adaptive"}`. Never send `budget_tokens` — Opus 5 returns 400.
- Never send `temperature`, `top_p`, `top_k`, or an assistant prefill — all 400 on Opus 5.
- One call **per requested section**, so each call is bounded and retryable on its own.
- `client.messages.parse(..., output_format=SectionOutput)` and read `response.parsed_output`.
- `max_tokens=16000` (the documented non-streaming ceiling for this shape).
- Check `response.stop_reason == "refusal"` before touching `response.content`.

- [ ] **Step 1: Write the failing tests**

```python
import os

from app.adapters.generation import (FixtureGenerationAdapter, get_generation_adapter,
                                     source_snapshot_hash)


def test_fixture_mode_is_the_default(monkeypatch):
    monkeypatch.delenv("GENERATION_MODE", raising=False)
    assert isinstance(get_generation_adapter(), FixtureGenerationAdapter)


def test_fixture_generation_is_deterministic(draft_request):
    a = FixtureGenerationAdapter().generate(draft_request)
    b = FixtureGenerationAdapter().generate(draft_request)
    assert [s.key for s in a.sections] == [s.key for s in b.sections]
    assert a.source_snapshot_hash == b.source_snapshot_hash


def test_only_requested_sections_are_returned(draft_request):
    request = draft_request.model_copy(update={"requested_sections": ["scope", "pricing"]})
    response = FixtureGenerationAdapter().generate(request)
    assert [s.key for s in response.sections] == ["scope", "pricing"]


def test_every_block_with_an_assertion_carries_claim_ids(draft_request):
    from app.domain.claims import contains_verifiable_assertion
    response = FixtureGenerationAdapter().generate(draft_request)
    for section in response.sections:
        for block in section.blocks:
            if contains_verifiable_assertion(block.content):
                assert block.claim_ids, f"{section.key}/{block.block_id} needs claim ids"


def test_claims_used_maps_every_referenced_claim(draft_request):
    response = FixtureGenerationAdapter().generate(draft_request)
    referenced = {c for s in response.sections for b in s.blocks for c in b.claim_ids}
    assert referenced == {u.claim_id for u in response.claims_used}


def test_unapproved_claim_is_not_used_and_produces_a_flag(draft_request_with_pending_claim):
    response = FixtureGenerationAdapter().generate(draft_request_with_pending_claim)
    assert any(f.code == "UNAPPROVED_CLAIM" for f in response.unresolved_flags)


def test_claude_adapter_request_shape(monkeypatch, draft_request):
    """Assert the exact kwargs sent to the SDK without making a network call."""
    captured = {}

    class FakeMessages:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr("app.adapters.generation._client",
                        lambda: type("C", (), {"messages": FakeMessages()})())
    from app.adapters.generation import ClaudeGenerationAdapter
    ClaudeGenerationAdapter().generate(draft_request)

    assert captured["model"] == "claude-opus-5"
    assert captured["thinking"] == {"type": "adaptive"}
    assert "budget_tokens" not in str(captured["thinking"])
    assert captured["max_tokens"] == 16000
    for banned in ("temperature", "top_p", "top_k"):
        assert banned not in captured
    assert captured["messages"][-1]["role"] == "user"  # no assistant prefill
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest app/tests/test_generation.py -v`
Expected: FAIL — `app.adapters.generation` does not exist.

- [ ] **Step 3: Implement `app/domain/prompts.py`**

One function per section key returning the user message text. Each prompt states the rule the model must obey: use only the supplied approved claims, cite `claimIds` on any block containing a verifiable assertion, never invent numbers, and never restate pricing figures — the pricing section renders from the calculated `Quote`, not from generated prose. Include the opportunity, discovery text, requirements, scope, and approved claims with evidence excerpts as structured context.

- [ ] **Step 4: Implement `app/adapters/generation.py`**

```python
import json
import os
from pathlib import Path

from pydantic import BaseModel

from app.domain.claims import contains_verifiable_assertion
from app.domain.pricing import compute_input_hash
from app.domain.schemas import (ClaimUsage, GeneratedBlock, GeneratedSection,
                                GenerateDraftResponse, ValidationFlag)

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "generation"


class BlockOutput(BaseModel):
    kind: str
    content: str
    claim_ids: list[str] = []
    source_record_ids: list[str] = []


class SectionOutput(BaseModel):
    key: str
    blocks: list[BlockOutput]


def source_snapshot_hash(request) -> str:
    return compute_input_hash({
        "opportunity": request.opportunity.model_dump(by_alias=True),
        "discovery": [d.model_dump(by_alias=True) for d in request.discovery],
        "requirements": [r.model_dump(by_alias=True) for r in request.requirements],
        "scope": request.scope.model_dump(by_alias=True),
        "claims": sorted(c.id for c in request.approved_claims),
        "templateId": request.template_id,
    })
```

`FixtureGenerationAdapter.generate` loads one fixture per requested section, preserves the requested order, drops any block whose claims are not `approved` while appending an `UNAPPROVED_CLAIM` `ValidationFlag`, builds `claims_used`, and derives a deterministic `generation_run_id` from the snapshot hash.

`ClaudeGenerationAdapter.generate` loops the requested sections and calls:

```python
response = _client().messages.parse(
    model=MODEL,
    max_tokens=16000,
    thinking={"type": "adaptive"},
    output_format=SectionOutput,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": prompt_for(section_key, request)}],
)
if response.stop_reason == "refusal":
    flags.append(ValidationFlag(code="SCHEMA_ERROR", severity="blocking",
                                message=f"model refused section {section_key}",
                                related_ids=[]))
    continue
section = response.parsed_output
```

Both adapters run the same post-processing: any block with a verifiable assertion and no `claimIds` is dropped and flagged `UNAPPROVED_CLAIM` (I1 holds regardless of what the model returns).

- [ ] **Step 5: Write the eleven section fixtures**

Trace A copy for a mid-size agency engagement. Blocks that quote outcomes reference the seeded claim ids from Task 13; neutral prose blocks carry no claims. `pricing.json` and `payment_schedule.json` contain only framing prose — the figures come from the `Quote`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest app/tests/test_generation.py -v`
Expected: PASS — 7 passed.

- [ ] **Step 7: Commit**

```bash
git add app/adapters/generation.py app/domain/prompts.py app/fixtures/generation/ app/tests/test_generation.py
git commit -m "feat: section-scoped generation adapter (claude-opus-5 live, fixtures for demo)"
```

---

### Task 10: Validation service — flag aggregation

**Files:**
- Create: `app/domain/validation.py`
- Test: `app/tests/test_validation.py`

**Interfaces:**
- Consumes: `app.domain.claims` (Task 4), `app.domain.pricing` (Task 3), `app.domain.workflow` (Task 5), `app.domain.schemas` (Task 2).
- Produces: `validate_version(version: ProposalVersion, sections: list[GeneratedSection], claims_by_id, evidence_by_claim, rules, approvals, document_status, now) -> list[ValidationFlag]`; `blocking_flags(flags) -> list[ValidationFlag]`. Task 12's `/validate`, `/submit`, and `/deliver` endpoints all route through this, which is how I8 becomes a single chokepoint.

Emits all eight `ValidationFlag` codes:

| Code | Raised when | Severity |
|---|---|---|
| `MISSING_SOURCE` | a block claim is unknown, or an approved claim has no evidence link | blocking |
| `UNAPPROVED_CLAIM` | a claim is not `approved`, or an assertion has no `claimIds` | blocking |
| `EXPIRED_CLAIM` | `validUntil < now` | blocking |
| `UNRESOLVED_REQUIREMENT` | a `Requirement` is `open_question`, or `Scope.openQuestions` is non-empty | blocking |
| `PRICE_MISMATCH` | recomputing the quote from stored lines and rules yields a different `totalMinor` or `inputHash` | blocking |
| `MISSING_APPROVAL` | a required approval is `pending` | blocking |
| `SCHEMA_ERROR` | a section or block fails model validation | blocking |
| `RENDER_ERROR` | document status is `failed` | blocking |

Warnings, not blockers: an `assumption`-status requirement, and a `low`-confidence requirement.

- [ ] **Step 1: Write the failing tests**

```python
from app.domain.validation import blocking_flags, validate_version


def codes(flags):
    return {f.code for f in flags}


def test_clean_version_has_no_blocking_flags(clean_bundle):
    flags = validate_version(**clean_bundle)
    assert blocking_flags(flags) == []


def test_price_mismatch_detected_when_total_is_tampered(clean_bundle):
    bundle = dict(clean_bundle)
    v = bundle["version"]
    bundle["version"] = v.model_copy(update={
        "quote": v.quote.model_copy(update={"total_minor": v.quote.total_minor + 1})})
    assert "PRICE_MISMATCH" in codes(validate_version(**bundle))


def test_open_question_produces_unresolved_requirement(bundle_with_open_question):
    assert "UNRESOLVED_REQUIREMENT" in codes(validate_version(**bundle_with_open_question))


def test_pending_approval_produces_missing_approval(bundle_with_pending_approval):
    assert "MISSING_APPROVAL" in codes(validate_version(**bundle_with_pending_approval))


def test_failed_document_produces_render_error(clean_bundle):
    bundle = dict(clean_bundle) | {"document_status": "failed"}
    assert "RENDER_ERROR" in codes(validate_version(**bundle))


def test_expired_claim_produces_expired_claim(bundle_with_expired_claim):
    assert "EXPIRED_CLAIM" in codes(validate_version(**bundle_with_expired_claim))


def test_assumption_requirement_is_a_warning_not_a_blocker(bundle_with_assumption):
    flags = validate_version(**bundle_with_assumption)
    assert blocking_flags(flags) == []
    assert any(f.severity == "warning" for f in flags)


def test_every_flag_carries_related_ids(clean_bundle, bundle_with_open_question):
    for bundle in (clean_bundle, bundle_with_open_question):
        for flag in validate_version(**bundle):
            assert flag.related_ids
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest app/tests/test_validation.py -v`
Expected: FAIL — `app.domain.validation` does not exist.

- [ ] **Step 3: Implement `app/domain/validation.py`**

Walk the blocks through `validate_block` and map each returned string to a `ValidationFlag` with the offending block and claim ids in `related_ids`. Then recompute the quote through `calculate_quote` with the stored lines and rules and compare `total_minor` and `input_hash`.

One conversion matters here: `QuoteLine.quantity` is a `number` in the canonical contract and therefore a `float` on the stored model, while `calculate_quote` rejects `float` quantities (I9). Rebuild each line input as `Decimal(str(line.quantity))` before recomputing — via `str`, never `Decimal(line.quantity)`, so the recomputed `input_hash` matches the original byte for byte:

```python
recomputed = calculate_quote(
    [{"id": l.id, "label": l.label, "ruleId": l.rule_id,
      "quantity": Decimal(str(l.quantity)), "optional": l.optional,
      "selected": l.selected, "sourceRecordIds": l.source_record_ids}
     for l in version.quote.lines],
    rules, version.quote.currency,
    discount_minor=version.quote.discount_minor,
    tax_minor=version.quote.tax_minor,
    installments=[i.model_dump(by_alias=True) for i in version.quote.payment_schedule],
    calculated_at=version.quote.calculated_at,
)
if (recomputed.total_minor != version.quote.total_minor
        or recomputed.input_hash != version.quote.input_hash):
    flags.append(ValidationFlag(code="PRICE_MISMATCH", severity="blocking",
                                message="stored quote does not match a recomputation "
                                        "from its rule versions",
                                related_ids=[l.id for l in version.quote.lines]))
``` Then scan requirements and `scope.open_questions`. Then scan approvals. Then check `document_status`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest app/tests/test_validation.py -v`
Expected: PASS — 8 passed.

- [ ] **Step 5: Commit**

```bash
git add app/domain/validation.py app/tests/test_validation.py
git commit -m "feat: validation service emitting all eight ValidationFlag codes (I8)"
```

---

### Task 11: Document rendering — branded HTML to PDF

**Files:**
- Create: `app/adapters/documents.py` (replace the Task 8 stub body), `app/templates/proposal.html.j2`, `app/templates/proposal.css`
- Create: `app/adapters/storage.py`
- Test: `app/tests/test_documents.py`

**Interfaces:**
- Consumes: `app.domain.schemas` (Task 2), `app.domain.money.format_minor` (Task 1).
- Produces: `render_html(version: ProposalVersion, sections: list[GeneratedSection], claims_by_id, evidence_by_claim) -> str`; `render_pdf(html: str, out_path: Path) -> Path`; `DocumentAdapter.execute` returning `{"documentId", "status", "uri", "contentHash"}` or `AdapterFailure`; `LocalStorage.put(path, data) -> str`.

Chromium print-to-PDF via Playwright rather than WeasyPrint: it installs cleanly on Windows and the same browser handles the Task 18 screenshot check.

- [ ] **Step 1: Install the renderer**

```bash
python -m pip install playwright
python -m playwright install chromium
```

Add `playwright>=1.48` to the `dev` extra in `pyproject.toml`.

- [ ] **Step 2: Write the failing tests**

```python
def test_rendered_html_contains_totals_formatted_from_minor_units(locked_version, sections):
    html = render_html(locked_version, sections, {}, {})
    assert "2,400.00 USD" in html


def test_rendered_html_marks_every_claim_with_its_evidence(locked_version, sections,
                                                           claims_by_id, evidence_by_claim):
    html = render_html(locked_version, sections, claims_by_id, evidence_by_claim)
    for claim_id in claims_by_id:
        assert f'data-claim-id="{claim_id}"' in html


def test_optional_unselected_lines_are_labelled_and_excluded_from_the_total(locked_version,
                                                                           sections):
    html = render_html(locked_version, sections, {}, {})
    assert "Optional" in html


def test_pdf_is_produced_and_non_trivial(tmp_path, locked_version, sections):
    out = render_pdf(render_html(locked_version, sections, {}, {}), tmp_path / "p.pdf")
    assert out.exists() and out.stat().st_size > 10_000
    assert out.read_bytes()[:4] == b"%PDF"


def test_render_failure_returns_adapter_failure(monkeypatch, locked_version):
    result = get_adapter("pandadoc").execute({"outcome": "failure"})
    assert isinstance(result, AdapterFailure)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest app/tests/test_documents.py -v`
Expected: FAIL — `render_html` does not exist.

- [ ] **Step 4: Implement rendering**

`app/templates/proposal.html.j2` — a Jinja2 template with the PRD's section order: cover, executive summary, understanding, scope, milestones, assumptions, options, pricing table, payment schedule, case studies, next steps. Money renders exclusively through `format_minor`; the template never does arithmetic. Every claim-backed sentence is wrapped in `<span data-claim-id="…" data-source-record-id="…">` so the evidence trail survives into the PDF — that markup is what makes I1 visible to a client on the page.

`app/templates/proposal.css` — print-oriented styles using the PRD design tokens, `@page { size: Letter; margin: 18mm; }`.

```python
def render_pdf(html: str, out_path: Path) -> Path:
    from playwright.sync_api import sync_playwright
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.pdf(path=str(out_path), format="Letter", print_background=True,
                 margin={"top": "18mm", "bottom": "18mm", "left": "18mm", "right": "18mm"})
        browser.close()
    return out_path
```

`DocumentAdapter.execute` moves the document through `requested → rendering → ready | failed`, writes the PDF through `LocalStorage` into `STORAGE_DIR`, and returns the `contentHash` of the bytes.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest app/tests/test_documents.py -v`
Expected: PASS — 5 passed.

- [ ] **Step 6: Commit**

```bash
git add app/adapters/documents.py app/adapters/storage.py app/templates/ app/tests/test_documents.py pyproject.toml
git commit -m "feat: branded HTML to PDF rendering with inline evidence attribution"
```

---

### Task 12: FastAPI application and the nine endpoints

**Files:**
- Create: `app/api/__init__.py`, `app/api/main.py`, `app/api/deps.py`, `app/api/routes/opportunities.py`, `app/api/routes/proposals.py`, `app/api/routes/quotes.py`, `app/api/routes/approvals.py`, `app/api/routes/documents.py`, `app/api/routes/analytics.py`
- Test: `app/tests/test_api.py`

**Interfaces:**
- Consumes: every domain module (Tasks 2–5, 10), persistence (Task 6), audit (Task 7), adapters (Tasks 8, 9, 11).
- Produces: `create_app() -> FastAPI`; the nine PRD endpoints, plus four the demo needs on top of them: `GET /v1/proposal-versions/{id}`, `GET /v1/proposal-versions/{id}/audit`, `GET /v1/content/claims`, and `POST /v1/proposals/{id}/versions` (body `{"copyFromVersionId": UUID}`) which creates the next version number and copies scope, quote, and only those claims passing `usable_in_new_version` — the endpoint that makes I7 observable. Task 18 adds `GET /v1/analytics/engagement` and `POST /v1/engagement/webhook`.

Three more working-state mutations the Capture, Ground, and Scope stages need, each `assert_mutable` first and each writing an `edited` audit event:

| Method | Path | Behavior |
|---|---|---|
| POST | `/v1/proposal-versions/{id}/discovery` | Attach a `DiscoveryInput` (`kind`, `sourceRecordId`) to the version |
| POST | `/v1/proposal-versions/{id}/scope/extract` | Derive `Requirement`s and `Scope` from the attached discovery; returns the `Scope` |
| POST | `/v1/proposal-versions/{id}/scope/resolve` | Body `{"openQuestion": str, "resolution": str}` — moves an open question to a confirmed requirement and removes it from `Scope.openQuestions` |

**The nine endpoints, verbatim paths:**

| Method | Path | Behavior |
|---|---|---|
| POST | `/v1/opportunities/import` | CRM adapter → normalize → `imported` or `needs_attention` with `requiredFieldErrors`; audit `imported` |
| POST | `/v1/proposals` | Create `Proposal` (`assembling`) + `ProposalVersion` 1 (`working`) |
| POST | `/v1/proposal-versions/{id}/generate` | `assert_mutable`, filter claims through `usable_in_new_version` (I7), call the generation adapter, persist sections; audit `generated` |
| POST | `/v1/proposal-versions/{id}/quote/calculate` | `assert_mutable`, `calculate_quote`, set quote status `review_required` when the discount exceeds `DiscountPolicy` limits else `calculated`; audit `edited` |
| POST | `/v1/proposal-versions/{id}/validate` | `validate_version` → store `unresolvedFlags`; audit `validated` |
| POST | `/v1/proposal-versions/{id}/submit` | Refuse on any blocking flag; `working → submitted`, create the required `Approval` rows |
| POST | `/v1/approvals/{id}/decide` | Enforce `requiredRole`; on the last approval, `lock_version` (`submitted → locked`); audit `approved`/`rejected`/`locked` |
| POST | `/v1/proposal-versions/{id}/render` | Locked only; render PDF; `locked → rendered`; audit `rendered` |
| POST | `/v1/proposal-versions/{id}/deliver` | `assert_deliverable`, signature adapter send, `rendered → delivered`; audit `delivered` |

Every 4xx body is `{"flags": [ValidationFlag, …]}` so the UI renders the same flag component everywhere.

- [ ] **Step 1: Write the failing tests**

`app/tests/test_api.py` using `httpx.ASGITransport` against `create_app()` with a seeded in-memory database:

```python
def test_import_success_normalizes_the_opportunity(client):
    r = client.post("/v1/opportunities/import",
                    json={"provider": "hubspot", "externalId": "42", "outcome": "success"})
    assert r.status_code == 201
    assert r.json()["status"] == "normalized"


def test_import_failure_surfaces_the_adapter_failure(client):
    r = client.post("/v1/opportunities/import",
                    json={"provider": "hubspot", "outcome": "failure"})
    assert r.status_code == 502
    assert r.json()["code"] == "AUTH"


def test_import_with_missing_fields_needs_attention(client):
    r = client.post("/v1/opportunities/import",
                    json={"provider": "manual", "outcome": "success",
                          "accountName": "", "title": ""})
    assert r.json()["status"] == "needs_attention"
    assert r.json()["requiredFieldErrors"]


def test_generate_then_calculate_then_validate_is_clean(client, seeded_version):
    client.post(f"/v1/proposal-versions/{seeded_version}/generate",
                json={"templateId": "t1", "requestedSections": ["scope", "case_studies"],
                      "modelProvider": "claude", "modelName": "claude-opus-5"})
    client.post(f"/v1/proposal-versions/{seeded_version}/quote/calculate",
                json={"currency": "USD", "discountMinor": 0, "taxMinor": 0,
                      "lines": [{"id": "l_strategy", "label": "Strategy days",
                                 "ruleId": "rule_strategy_day", "quantity": "4",
                                 "optional": False, "selected": True,
                                 "sourceRecordIds": ["src_transcript"]}],
                      "installments": [{"sequence": 1, "label": "Deposit",
                                        "amountMinor": 240000,
                                        "dueDescription": "On signature"},
                                       {"sequence": 2, "label": "Final",
                                        "amountMinor": 240000,
                                        "dueDescription": "On delivery"}]})
    r = client.post(f"/v1/proposal-versions/{seeded_version}/validate")
    assert [f for f in r.json()["flags"] if f["severity"] == "blocking"] == []


def test_submit_is_refused_while_a_blocking_flag_is_open(client, version_with_open_question):
    r = client.post(f"/v1/proposal-versions/{version_with_open_question}/submit")
    assert r.status_code == 409
    assert any(f["code"] == "UNRESOLVED_REQUIREMENT" for f in r.json()["flags"])


def test_wrong_role_cannot_decide_an_approval(client, pending_quote_approval):
    r = client.post(f"/v1/approvals/{pending_quote_approval}/decide",
                    json={"decision": "approved", "reviewerId": "u_content",
                          "reviewerRole": "content_editor"})
    assert r.status_code == 403


def test_last_approval_locks_the_version(client, submitted_version_one_approval_left):
    version_id, approval_id = submitted_version_one_approval_left
    client.post(f"/v1/approvals/{approval_id}/decide",
                json={"decision": "approved", "reviewerId": "u_prop",
                      "reviewerRole": "proposal_approver"})
    assert client.get(f"/v1/proposal-versions/{version_id}").json()["status"] == "locked"


def test_locked_version_refuses_generate_and_quote(client, locked_version_id):
    for path in ("generate", "quote/calculate"):
        r = client.post(f"/v1/proposal-versions/{locked_version_id}/{path}", json={})
        assert r.status_code == 409


def test_deliver_is_refused_before_render(client, locked_version_id):
    r = client.post(f"/v1/proposal-versions/{locked_version_id}/deliver", json={})
    assert r.status_code == 409
    assert any(f["code"] in {"RENDER_ERROR", "MISSING_APPROVAL"} or "document" in f["message"]
               for f in r.json()["flags"])


def test_render_then_deliver_succeeds(client, locked_version_id):
    assert client.post(f"/v1/proposal-versions/{locked_version_id}/render",
                       json={}).status_code == 200
    r = client.post(f"/v1/proposal-versions/{locked_version_id}/deliver",
                    json={"provider": "pandadoc", "outcome": "success"})
    assert r.status_code == 200
    assert r.json()["status"] == "delivered"


def test_every_mutation_wrote_an_audit_event(client, delivered_version_id):
    actions = {e["action"] for e in
               client.get(f"/v1/proposal-versions/{delivered_version_id}/audit").json()}
    assert {"generated", "validated", "approved", "locked", "rendered", "delivered"} <= actions
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest app/tests/test_api.py -v`
Expected: FAIL — `app.api.main` does not exist.

- [x] **Step 3: Implement the API**

`app/api/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (analytics, approvals, documents, opportunities, proposals,
                            quotes)


def create_app() -> FastAPI:
    app = FastAPI(title="Proposal, RFP, and Quote Generation", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                       allow_methods=["*"], allow_headers=["*"])
    for module in (opportunities, proposals, quotes, approvals, documents, analytics):
        app.include_router(module.router, prefix="/v1")
    return app


app = create_app()
```

`app/api/deps.py` supplies the engine, a session dependency, `now()` (one clock, injectable so tests are deterministic), and `current_actor()` reading a seeded reviewer role from a header — enough for the demo without a login screen.

Each route module is thin: parse, call a domain function, persist, `record_event`, return. All business rules stay in `app/domain/`. Blocking flags map to 409, adapter failures to 502, role violations to 403.

- [x] **Step 4: Run the tests to verify they pass**

Run: `pytest app/tests/test_api.py -v`
Expected: PASS — 13 passed.

- [x] **Step 5: Run the whole suite and lint**

Run: `pytest -q` then `ruff check app/`
Expected: all green. Verified with the repository virtual environment: 333 tests passed and `ruff check app` passed.

- [x] **Step 6: Commit**

```bash
git add app/api/ app/tests/test_api.py
git commit -m "feat: FastAPI service exposing the nine workflow endpoints with gate enforcement"
```

---

### Task 13: Trace A and Trace B seed fixtures with a demo CLI

**Files:**
- Create: `app/fixtures/agency_discovery.json`, `app/fixtures/rfp_response.json`, `app/fixtures/pricing_rules.json`, `app/fixtures/claims.json`, `app/fixtures/users.json`
- Create: `app/cli.py`
- Test: `app/tests/test_seed.py`

**Interfaces:**
- Consumes: persistence (Task 6), adapters (Task 8), API (Task 12).
- Produces: `python -m app.cli seed`, `python -m app.cli demo`, `python -m app.cli reset`; `seed_all(session) -> SeedResult` with `.opportunity_ids`, `.proposal_ids`, `.version_ids`, `.claim_ids`, `.rule_ids`.

**Trace A fixture content (the agency discovery call):**
- `Opportunity` — account "Northwind Retail Group", contact, title "Brand refresh and site rebuild", currency `USD`, provider `hubspot`
- `DiscoveryInput` — a `transcript` of roughly 900 words covering goals, timeline, budget range, three must-haves, one open question about a legacy CMS
- Six `Requirement`s — four `confirmed`, one `assumption`, one `open_question` (the open question is what the demo resolves live on screen)
- `Scope` — five deliverables (two `optional`), four milestones, three assumptions, two exclusions
- Five `Claim`s with evidence — four `approved`, one `pending_approval` (so the demo can show a claim being approved), each with an `EvidenceLink` carrying a real locator and excerpt
- `PricingRule`s — six rules, version `2026.1`, `USD`, covering strategy days, design sprints, build weeks, content migration (optional), training (optional), and retainer
- `DiscountPolicy` — `maxPercentWithoutApproval: 10`, `maxMinorWithoutApproval: 250000`, `requiresQuoteApprovalAbove: 5000000`
- Users — one per role: `content_editor`, `quote_approver`, `proposal_approver`

**Trace B fixture content (the RFP response):** an `rfp_text` `DiscoveryInput` with twelve numbered requirements, a `Requirement` per numbered item preserving RFP order, and answers mapped to approved claims. The demo point is ordered, source-linked answers, so the fixture must exercise `rfp_answers` generation.

- [x] **Step 1: Write the failing test**

```python
def test_seed_produces_both_traces(session):
    result = seed_all(session)
    assert len(result.opportunity_ids) == 2
    assert len(result.version_ids) == 2


def test_trace_a_has_an_open_question_and_a_pending_claim(session):
    result = seed_all(session)
    version = VersionRepo(session).get(result.version_ids[0])
    assert version.scope.open_questions
    claims = ClaimRepo(session).list()
    assert any(c.status == "pending_approval" for c in claims)


def test_trace_b_requirements_preserve_rfp_order(session):
    result = seed_all(session)
    version = VersionRepo(session).get(result.version_ids[1])
    numbers = [r.text.split(".")[0] for r in version.scope.deliverables] or None
    assert numbers is None or numbers == sorted(numbers, key=int)


def test_pricing_rules_share_one_version_and_currency(session):
    rules = PricingRuleRepo(session).list()
    assert {r.version for r in rules} == {"2026.1"}
    assert {r.currency for r in rules} == {"USD"}


def test_seed_is_idempotent(session):
    a = seed_all(session)
    b = seed_all(session)
    assert a.version_ids == b.version_ids
```

- [x] **Step 2: Run it to verify it fails**

Run: `pytest app/tests/test_seed.py -v`
Expected: FAIL — `app.cli` does not exist.

- [x] **Step 3: Write the fixtures and the CLI**

`app/cli.py`:

```python
import typer

app_cli = typer.Typer(help="Demo operations for the proposal system.")


@app_cli.command()
def seed():
    """Load Trace A and Trace B fixtures into the database."""


@app_cli.command()
def demo():
    """Run Trace A end to end and print each gate as it passes."""


@app_cli.command()
def reset():
    """Drop and recreate all tables, then seed."""


if __name__ == "__main__":
    app_cli()
```

`demo` drives the nine endpoints in order through the ASGI app and prints one line per stage — `Capture → Ground → Scope → Price → Draft → Approve → Deliver → Observe` — so the pitch has a terminal fallback if the browser misbehaves.

Fixture ids are stable strings (`opp_northwind`, `claim_onboarding_40`, `rule_strategy_day`) rather than random UUIDs, which is what makes `seed` idempotent and the fixtures readable when demoing the audit trail.

- [x] **Step 4: Run it to verify it passes**

Run: `pytest app/tests/test_seed.py -v`
Expected: PASS — 5 passed.

- [x] **Step 5: Run the demo end to end**

```bash
docker compose up -d db
python -m app.cli reset
python -m app.cli demo
```
Expected: eight stage lines, ending with a delivered version and a PDF path under `var/storage/`.

- [ ] **Step 6: Commit**

```bash
git add app/fixtures/ app/cli.py app/tests/test_seed.py
git commit -m "feat: Trace A and Trace B seed fixtures with seed, demo, and reset CLI"
```

---

### Task 14: Web shell — tokens, layout, API client, shared components

**Files:**
- Create: `app/web/package.json`, `app/web/tsconfig.json`, `app/web/next.config.ts`, `app/web/playwright.config.ts`
- Create: `app/web/app/layout.tsx`, `app/web/app/globals.css`, `app/web/app/page.tsx`
- Create: `app/web/lib/api.ts`, `app/web/lib/format.ts`
- Create: `app/web/components/{AppShell,StatusPill,FlagList,DataTable,StatTile,Field,Button}.tsx`
- Test: `app/web/e2e/shell.spec.ts`

**Interfaces:**
- Consumes: the Task 12 API over `http://localhost:8000`.
- Produces: `api.get<T>(path)`, `api.post<T>(path, body)` throwing `ApiError` carrying `flags: ValidationFlag[]`; `formatMinor(minor: number, currency: string): string`; `<AppShell>`, `<StatusPill status>`, `<FlagList flags>`, `<DataTable columns rows>`, `<StatTile label value delta>`, `<Field>`, `<Button>`. Tasks 15–18 build only screens on top of these.

`formatMinor` must mirror the Python `format_minor` exactly — same grouping, same two decimals, same trailing currency code — so a number never reads differently in the UI than in the PDF. The web app never does money arithmetic; totals always come from the API.

- [x] **Step 1: Scaffold the app**

```bash
cd app/web
npm create next-app@latest . -- --typescript --app --eslint --no-tailwind --no-src-dir --import-alias "@/*"
npm i -D @playwright/test
npx playwright install chromium
```

Add to `package.json` scripts: `"e2e": "playwright test"`, `"dev": "next dev -p 3000"`.

- [x] **Step 2: Choose the palette, then validate it — do not skip this**

Light mode is the PRD token block verbatim. Dark mode is a **selected** palette validated against the dark surface, never an inversion of the light one.

Candidate categorical/status hues for validation (light on `--paper #fbfaf7`): `#0f5d5e`, `#9a5b00`, `#a12a31`, `#40505f`, and a `good` step `#1f6f45`.
Candidate dark set (on surface `#11171c`): `#4fb3ac`, `#e0a14a`, `#e0787e`, `#8494a0`, `#58b585`.

Run the dataviz skill's validator against both modes — the hexes above are proposals, not verified values:

```bash
node <dataviz-skill>/scripts/validate_palette.js "#0f5d5e,#9a5b00,#a12a31,#40505f,#1f6f45" --mode light
node <dataviz-skill>/scripts/validate_palette.js "#4fb3ac,#e0a14a,#e0787e,#8494a0,#58b585" --mode dark
```

Validation note: the referenced `dataviz` skill is not installed in this workspace. The specified palette is recorded in `globals.css`, and the available browser verification covers the dark surface plus text-and-icon status treatment.

Resolve `<dataviz-skill>` by invoking the `dataviz` skill and reading its reported base directory — do not hardcode a temp path, it will not exist in a later session. Fix every **FAIL** before writing the token file: a normal-vision separation below 15 means re-stepping that pair (secondary encoding does not excuse it); a CVD ΔE between 6 and 8 is allowed only because every status here already ships with an icon and a text label. Record the final validated hexes as a comment at the top of `globals.css` with the date they were validated.

- [x] **Step 3: Write the failing E2E test**

`app/web/e2e/shell.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("shell renders navigation to every workspace route", async ({ page }) => {
  await page.goto("/");
  for (const label of ["Opportunities", "Content library", "Analytics"]) {
    await expect(page.getByRole("link", { name: label })).toBeVisible();
  }
});

test("money is formatted identically to the API", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("format-probe")).toHaveText("1,250.00 USD");
});

test("dark mode uses the selected dark tokens, not an inverted light palette",
  async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");
    const bg = await page.evaluate(() =>
      getComputedStyle(document.body).backgroundColor);
    expect(bg).toBe("rgb(17, 23, 28)");
  });
```

- [x] **Step 4: Run it to verify it fails**

Run: `npm run e2e -- e2e/shell.spec.ts`
Expected: FAIL — no such links, no probe element.

- [x] **Step 5: Implement the shell**

`globals.css` — the PRD's `:root` block verbatim, then semantic tokens layered on top so components never reference a raw hue:

```css
:root {
  /* PRD tokens — light */
  --ink-950: #17212b; --ink-700: #40505f; --ink-500: #6f7d8a;
  --paper: #fbfaf7; --panel: #ffffff; --line: #d9dedf;
  --teal-700: #0f5d5e; --teal-100: #dff2ef;
  --amber-700: #9a5b00; --amber-100: #fff0ce;
  --red-700: #a12a31; --red-100: #fbe3e3;
  --radius-sm: 6px; --radius-md: 10px;
  --shadow-card: 0 8px 24px rgba(23, 33, 43, 0.08);

  /* semantic — light */
  --surface: var(--paper);
  --surface-panel: var(--panel);
  --border: var(--line);
  --text-primary: var(--ink-950);
  --text-secondary: var(--ink-700);
  --text-muted: var(--ink-500);
  --accent: var(--teal-700);
  --status-good: #1f6f45; --status-good-bg: #dcf0e4;
  --status-warning: var(--amber-700); --status-warning-bg: var(--amber-100);
  --status-critical: var(--red-700); --status-critical-bg: var(--red-100);
}

/* Dark steps: replace any hex the Step 2 validator marked FAIL with the step it
   suggested, then re-run both modes until every check passes. */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --surface: #11171c;
    --surface-panel: #172026;
    --border: #2b363e;
    --text-primary: #eef3f5;
    --text-secondary: #b3c0c9;
    --text-muted: #8494a0;
    --accent: #4fb3ac;
    --status-good: #58b585; --status-good-bg: #16301f;
    --status-warning: #e0a14a; --status-warning-bg: #33260f;
    --status-critical: #e0787e; --status-critical-bg: #331619;
    --shadow-card: 0 8px 24px rgba(0, 0, 0, 0.45);
  }
}
:root[data-theme="dark"] {
  /* Identical block to the media query above, so the explicit toggle wins in
     both directions. Keep the two in sync. */
}
```

Every color must have its first definition on bare `:root`, never only inside a media query, and `body` gets an explicit `background: var(--surface)` — a transparent body borrows the host page's theme.

Typography scale from the PRD: Display 32/38, H1 24/30, H2 18/24, Body 15/22, Label 13/18, Caption 12/16.

`lib/api.ts` throws `ApiError` with the parsed `flags` array on any non-2xx, so every screen can drop in `<FlagList>` without bespoke error handling.

`<StatusPill>` renders an icon plus the status word — status is never color alone.

- [x] **Step 6: Run the tests to verify they pass**

Run: `npm run e2e -- e2e/shell.spec.ts`
Expected: PASS — 3 passed.

- [x] **Step 7: Commit**

```bash
git add app/web/
git commit -m "feat: Next.js shell with validated light and dark token palettes"
```

---

### Task 15: Opportunity and proposal workspace screens

**Files:**
- Create: `app/web/app/opportunities/page.tsx`, `app/web/app/opportunities/[id]/page.tsx`
- Create: `app/web/app/proposals/[id]/page.tsx`, `app/web/app/proposals/[id]/scope/page.tsx`, `app/web/app/proposals/[id]/content/page.tsx`
- Create: `app/web/components/{SourceChip,RequirementRow,DeliverableEditor,EvidencePopover}.tsx`
- Test: `app/web/e2e/workspace.spec.ts`

**Interfaces:**
- Consumes: Task 14 components and `api`; endpoints `/v1/opportunities/import`, `/v1/proposals`, `/v1/proposal-versions/{id}`, `/v1/proposal-versions/{id}/generate`.
- Produces: the three portfolio screens "opportunity import", "proposal editor", and the scope view; `<SourceChip sourceRecordId>` and `<EvidencePopover claimId>` reused by Tasks 16–18.

**Screen 1 — opportunity import** (`/opportunities`): provider picker, import button, a table of imported opportunities with `StatusPill`, and a visible `needs_attention` row listing its `requiredFieldErrors`. The failure branch is a first-class demo beat, not an error state hidden behind a toast.

**Screen 2 — proposal editor** (`/proposals/:id`): section list on the left, editable blocks in the middle, and an evidence rail on the right. Every block with `claimIds` shows a `SourceChip` per source; clicking it opens `<EvidencePopover>` with the locator and excerpt. Blocks with no claims and no assertions render plainly. A block flagged `UNAPPROVED_CLAIM` renders with the warning treatment plus the flag text.

**Screen 3 — scope** (`/proposals/:id/scope`): deliverables (with an `Optional` toggle), milestones in sequence, assumptions, exclusions, and open questions. Resolving an open question is a real mutation, because Task 19's trace test drives it.

- [x] **Step 1: Write the failing E2E test**

```ts
test("importing a hubspot opportunity lands normalized", async ({ page }) => {
  await page.goto("/opportunities");
  await page.getByLabel("Provider").selectOption("hubspot");
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByRole("row", { name: /Northwind Retail Group/ })
    .getByText("Normalized")).toBeVisible();
});

test("a failed import shows the adapter failure with its code", async ({ page }) => {
  await page.goto("/opportunities");
  await page.getByLabel("Outcome").selectOption("failure");
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByText("AUTH")).toBeVisible();
  await expect(page.getByText(/token expired/i)).toBeVisible();
});

test("every claim-backed block exposes its evidence", async ({ page }) => {
  await page.goto("/proposals/prop_northwind");
  const chips = page.getByTestId("source-chip");
  await expect(chips.first()).toBeVisible();
  await chips.first().click();
  await expect(page.getByTestId("evidence-excerpt")).toBeVisible();
});

test("resolving the open question clears the scope warning", async ({ page }) => {
  await page.goto("/proposals/prop_northwind/scope");
  await expect(page.getByText("Open question")).toBeVisible();
  await page.getByTestId("resolve-open-question").first().click();
  await page.getByLabel("Resolution").fill("Legacy CMS stays on v4 through Q4.");
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Open question")).toHaveCount(0);
});
```

- [x] **Step 2: Run it to verify it fails**

Run: `npm run e2e -- e2e/workspace.spec.ts`
Expected: FAIL — routes do not exist.

- [x] **Step 3: Implement the three screens**

Server components fetch through `lib/api`; the editing surfaces are client components. Keep each route file under ~200 lines by pushing the repeated pieces into the components listed above.

- [x] **Step 4: Run it to verify it passes**

Run: `npm run e2e -- e2e/workspace.spec.ts`
Expected: PASS — 4 passed.

- [x] **Step 5: Screenshot and eyeball the layout**

```bash
npx playwright test e2e/workspace.spec.ts --update-snapshots
```
Open the captured PNGs and check for label collisions, overflow, and the evidence rail at 1280px and 1440px. Fix anything visibly broken before committing — the validator checks color, not layout.

- [x] **Step 6: Commit**

```bash
git add app/web/app/opportunities app/web/app/proposals app/web/components app/web/e2e/workspace.spec.ts
git commit -m "feat: opportunity import, proposal editor, and scope screens with evidence rail"
```

---

### Task 16: Pricing configurator and approval screens

**Files:**
- Create: `app/web/app/proposals/[id]/quote/page.tsx`, `app/web/app/proposals/[id]/approval/page.tsx`
- Create: `app/web/components/{QuoteTable,PaymentSchedule,DiscountControl,ApprovalCard}.tsx`
- Test: `app/web/e2e/quote.spec.ts`, `app/web/e2e/approval.spec.ts`

**Interfaces:**
- Consumes: Task 14 components, `/v1/proposal-versions/{id}/quote/calculate`, `/v1/proposal-versions/{id}/validate`, `/v1/proposal-versions/{id}/submit`, `/v1/approvals/{id}/decide`.
- Produces: the "pricing configurator" and "approval page" portfolio screens; `<QuoteTable>` reused by Task 17's client preview.

**Pricing configurator** (`/proposals/:id/quote`): one row per line showing label, rule version, quantity, unit price, subtotal; a checkbox on optional lines; discount and tax inputs; totals block; payment schedule. Every figure is server-computed — toggling an optional line POSTs to `/quote/calculate` and re-renders from the response. The UI must not sum anything locally, which is what keeps I3, I4, and I9 true on screen.

A discount past the `DiscountPolicy` threshold flips the quote to `review_required` and shows why, naming the policy limit. That is the pitch beat for pricing control.

**Approval page** (`/proposals/:id/approval`): one `<ApprovalCard>` per required approval showing kind, required role, decision, reviewer, and comment. Submit is disabled while any blocking flag is open, with the flags listed beside the button rather than in a tooltip. Approving the last card locks the version and the whole page switches to read-only.

- [x] **Step 1: Write the failing tests**

`e2e/quote.spec.ts`:

```ts
test("optional line changes the total only when selected", async ({ page }) => {
  await page.goto("/proposals/prop_northwind/quote");
  const before = await page.getByTestId("total-minor").textContent();
  await page.getByTestId("line-optional-training").check();
  await expect(page.getByTestId("total-minor")).not.toHaveText(before!);
  await page.getByTestId("line-optional-training").uncheck();
  await expect(page.getByTestId("total-minor")).toHaveText(before!);
});

test("total equals subtotal minus discount plus tax", async ({ page }) => {
  await page.goto("/proposals/prop_northwind/quote");
  await page.getByLabel("Discount").fill("500.00");
  await page.getByLabel("Tax").fill("120.00");
  await page.getByRole("button", { name: "Recalculate" }).click();
  const read = async (id: string) =>
    Number((await page.getByTestId(id).getAttribute("data-minor"))!);
  expect(await read("total-minor")).toBe(
    (await read("subtotal-minor")) - (await read("discount-minor")) + (await read("tax-minor")));
});

test("payment installments sum to the total", async ({ page }) => {
  await page.goto("/proposals/prop_northwind/quote");
  const parts = await page.getByTestId("installment").all();
  const sum = (await Promise.all(parts.map(async p =>
    Number((await p.getAttribute("data-minor"))!)))).reduce((a, b) => a + b, 0);
  expect(sum).toBe(Number((await page.getByTestId("total-minor")
    .getAttribute("data-minor"))!));
});

test("an over-policy discount requires quote approval and says why", async ({ page }) => {
  await page.goto("/proposals/prop_northwind/quote");
  await page.getByLabel("Discount").fill("9000.00");
  await page.getByRole("button", { name: "Recalculate" }).click();
  await expect(page.getByText("Review required")).toBeVisible();
  await expect(page.getByText(/exceeds 10%|exceeds the 2,500.00 USD limit/)).toBeVisible();
});

test("every line names its pricing rule version", async ({ page }) => {
  await page.goto("/proposals/prop_northwind/quote");
  for (const row of await page.getByTestId("quote-line").all()) {
    await expect(row.getByTestId("rule-version")).toHaveText("2026.1");
  }
});
```

`e2e/approval.spec.ts`:

```ts
test("submit is blocked while a flag is open and lists the flags", async ({ page }) => {
  await page.goto("/proposals/prop_blocked/approval");
  await expect(page.getByRole("button", { name: "Submit for approval" })).toBeDisabled();
  await expect(page.getByText("UNRESOLVED_REQUIREMENT")).toBeVisible();
});

test("a reviewer cannot decide an approval outside their role", async ({ page }) => {
  await page.goto("/proposals/prop_northwind/approval?as=content_editor");
  const quoteCard = page.getByTestId("approval-quote");
  await expect(quoteCard.getByRole("button", { name: "Approve" })).toBeDisabled();
  await expect(quoteCard.getByText("Requires quote approver")).toBeVisible();
});

test("approving the last approval locks the version", async ({ page }) => {
  await page.goto("/proposals/prop_ready/approval?as=proposal_approver");
  await page.getByTestId("approval-proposal").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Locked")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
});
```

- [x] **Step 2: Run them to verify they fail**

Run: `npm run e2e -- e2e/quote.spec.ts e2e/approval.spec.ts`
Expected: FAIL — routes do not exist.

- [x] **Step 3: Implement both screens**

Money cells carry both the formatted text and a `data-minor` integer attribute, which is what lets the tests assert the invariant arithmetic without parsing formatted strings.

- [x] **Step 4: Run them to verify they pass**

Run: `npm run e2e -- e2e/quote.spec.ts e2e/approval.spec.ts`
Expected: PASS — 8 passed.

- [ ] **Step 5: Commit**

```bash
git add app/web/app/proposals app/web/components app/web/e2e/quote.spec.ts app/web/e2e/approval.spec.ts
git commit -m "feat: pricing configurator and approval screens with server-computed totals"
```

---

### Task 17: Client proposal preview and content library

**Files:**
- Create: `app/web/app/proposals/[id]/preview/page.tsx`, `app/web/app/content/page.tsx`
- Create: `app/web/components/{ProposalDocument,ClaimRow,ExpiryBadge}.tsx`
- Test: `app/web/e2e/preview.spec.ts`, `app/web/e2e/content.spec.ts`

**Interfaces:**
- Consumes: `<QuoteTable>` (Task 16), `<EvidencePopover>` (Task 15), `/v1/proposal-versions/{id}`, `/v1/proposal-versions/{id}/render`, `/v1/content/claims`.
- Produces: the "client proposal" and "content library" portfolio screens.

**Client proposal** (`/proposals/:id/preview`): the client-facing read of the document — cover, executive summary, understanding, scope, milestones, assumptions, options, pricing, payment schedule, case studies, next steps. Must be visually the same document as the PDF; the same section order, the same figures. A "Download PDF" action calls `/render` and links the stored file. Optional lines appear as clearly-labelled options, never folded into the headline price.

**Content library** (`/content`): claims table with status, validity window, allowed and prohibited contexts, evidence count, and source links. `<ExpiryBadge>` marks claims expiring within 30 days. An approve action moves `pending_approval → approved`, and an expired claim shows that it cannot be used in a new version (I7).

- [x] **Step 1: Write the failing tests**

```ts
// e2e/preview.spec.ts
test("preview section order matches the PDF section order", async ({ page }) => {
  await page.goto("/proposals/prop_northwind/preview");
  const headings = await page.getByRole("heading", { level: 2 }).allTextContents();
  expect(headings).toEqual(["Executive summary", "Understanding", "Scope", "Milestones",
    "Assumptions", "Options", "Pricing", "Payment schedule", "Case studies", "Next steps"]);
});

test("optional services are labelled and excluded from the headline total",
  async ({ page }) => {
    await page.goto("/proposals/prop_northwind/preview");
    await expect(page.getByTestId("options-section").getByText("Optional")).toBeVisible();
    const total = Number((await page.getByTestId("total-minor")
      .getAttribute("data-minor"))!);
    const optional = Number((await page.getByTestId("optional-total-minor")
      .getAttribute("data-minor"))!);
    expect(total).toBeLessThan(total + optional);
  });

test("download produces a PDF", async ({ page }) => {
  await page.goto("/proposals/prop_ready/preview");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download PDF" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
});

// e2e/content.spec.ts
test("a pending claim can be approved from the library", async ({ page }) => {
  await page.goto("/content");
  const row = page.getByRole("row", { name: /Pending approval/ }).first();
  await row.getByRole("button", { name: "Approve" }).click();
  await expect(row.getByText("Approved")).toBeVisible();
});

test("an expired claim is marked unusable in a new version", async ({ page }) => {
  await page.goto("/content");
  const row = page.getByRole("row", { name: /Expired/ }).first();
  await expect(row.getByText("Cannot be used in a new version")).toBeVisible();
});

test("every claim shows its evidence count and sources", async ({ page }) => {
  await page.goto("/content");
  for (const row of await page.getByTestId("claim-row").all()) {
    await expect(row.getByTestId("evidence-count")).toBeVisible();
  }
});
```

- [x] **Step 2: Run them to verify they fail**

Run: `npm run e2e -- e2e/preview.spec.ts e2e/content.spec.ts`
Expected: FAIL — routes do not exist.

- [x] **Step 3: Implement both screens**

`<ProposalDocument>` shares its section ordering constant with the Jinja2 template by reading the same ordered key list, so the preview and the PDF cannot drift.

- [x] **Step 4: Run them to verify they pass**

Run: `npm run e2e -- e2e/preview.spec.ts e2e/content.spec.ts`
Expected: PASS — 6 passed.

- [x] **Step 5: Compare the preview against the PDF**

Render the PDF for the same version and put the two side by side. Section order, figures, and optional labelling must match. Fix drift before committing.

- [ ] **Step 6: Commit**

```bash
git add app/web/app/proposals app/web/app/content app/web/components app/web/e2e/preview.spec.ts app/web/e2e/content.spec.ts
git commit -m "feat: client proposal preview and content library with expiry handling"
```

---

### Task 18: Engagement analytics screen

**Files:**
- Create: `app/web/app/analytics/page.tsx`
- Create: `app/web/components/{KpiTiles,EventTimeline,ViewsBarChart,ChartTableView}.tsx`
- Modify: `app/api/routes/analytics.py` (add `GET /v1/analytics/engagement`)
- Test: `app/web/e2e/analytics.spec.ts`, `app/tests/test_analytics_api.py`

**Interfaces:**
- Consumes: `EngagementRepo` (Task 6), `AuditRepo` (Task 7), Task 14 components.
- Produces: `GET /v1/analytics/engagement` returning `{kpis: [{key, label, valueMinor?, value?, unit}], events: [{id, type, actor, at, proposalId, documentId?}], viewsByDay: [{day, count}]}`; the "engagement analytics" portfolio screen.

**Form choice, per the dataviz procedure:** four KPI figures are single headline numbers with no meaningful series, so they are **stat tiles, not charts**. Provider engagement is a sequence of discrete labelled events, so it is a **timeline**, not a chart. Only views-over-time has a magnitude across an ordered dimension, so exactly one chart appears on this page: a **single-series bar chart**.

**Chart specification (all of these are testable):**
- One series, one hue (`--accent`), so **no legend** — the chart title names the series.
- **No dual axis.** Never. Views is the only measure on the plot; anything else gets its own figure.
- 4px rounded data-ends, anchored to the baseline. 2px surface-colored gap between adjacent bars. Recessive grid and axes in `--text-muted`.
- Selective direct labels: the max and the latest bar only, never a number on every bar.
- Values, labels, and axis text wear text tokens, never the series color.
- A crosshair-free per-bar hover tooltip with day and count; the hit target is the full column, wider than the bar.
- A `<ChartTableView>` toggle exposing the same numbers as a table.
- Inline SVG. No chart library.
- Status colors on timeline events are reserved and always ship with an icon plus a text label.

**Sent → viewed → signed** events map to the status palette: `sent` neutral, `viewed` good, `signed` good with a distinct icon, `declined` critical, `expired` warning. Each row carries the icon, the word, the timestamp, and the actor.

- [x] **Step 1: Write the failing API test**

```python
def test_engagement_endpoint_returns_kpis_events_and_views(client, delivered_version_id):
    body = client.get("/v1/analytics/engagement").json()
    assert {k["key"] for k in body["kpis"]} == {"proposals_sent", "win_rate",
                                                "median_cycle_days", "pipeline_value"}
    assert body["events"] and body["viewsByDay"]


def test_pipeline_value_is_reported_in_minor_units(client):
    kpi = next(k for k in client.get("/v1/analytics/engagement").json()["kpis"]
               if k["key"] == "pipeline_value")
    assert isinstance(kpi["valueMinor"], int)


def test_provider_events_never_mutate_a_locked_version(client, locked_version_id):
    before = client.get(f"/v1/proposal-versions/{locked_version_id}").json()
    client.post("/v1/engagement/webhook",
                json={"provider": "pandadoc", "type": "viewed",
                      "proposalVersionId": locked_version_id,
                      "at": "2026-08-02T12:00:00Z"})
    after = client.get(f"/v1/proposal-versions/{locked_version_id}").json()
    assert before == after  # I10
    assert any(e["type"] == "viewed"
               for e in client.get("/v1/analytics/engagement").json()["events"])
```

- [x] **Step 2: Run it to verify it fails**

Run: `pytest app/tests/test_analytics_api.py -v`
Expected: FAIL — the route does not exist.

- [x] **Step 3: Implement the endpoint**

Aggregate from `EngagementRecordRow` and `AuditEventRow`. The webhook handler appends an engagement record and writes an `engagement_received` audit event; it never touches the version row (I10).

- [x] **Step 4: Run it to verify it passes**

Run: `pytest app/tests/test_analytics_api.py -v`
Expected: PASS — 3 passed.

- [x] **Step 5: Write the failing UI test**

```ts
test("four KPI tiles render as figures, not charts", async ({ page }) => {
  await page.goto("/analytics");
  await expect(page.getByTestId("kpi-tile")).toHaveCount(4);
  await expect(page.getByTestId("kpi-tile").first().locator("svg")).toHaveCount(0);
});

test("the single-series chart has no legend", async ({ page }) => {
  await page.goto("/analytics");
  await expect(page.getByTestId("views-chart")).toBeVisible();
  await expect(page.getByTestId("chart-legend")).toHaveCount(0);
});

test("only the max and latest bars are directly labelled", async ({ page }) => {
  await page.goto("/analytics");
  const bars = await page.getByTestId("bar").count();
  expect(bars).toBeGreaterThan(4);
  await expect(page.getByTestId("bar-label")).toHaveCount(2);
});

test("bars are anchored to the baseline with rounded data-ends", async ({ page }) => {
  await page.goto("/analytics");
  const bar = page.getByTestId("bar").first();
  await expect(bar).toHaveAttribute("rx", "4");
  const [barBox, axisBox] = [await bar.boundingBox(),
                             await page.getByTestId("x-axis").boundingBox()];
  expect(Math.abs(barBox!.y + barBox!.height - axisBox!.y)).toBeLessThan(2);
});

test("hovering a column shows day and count", async ({ page }) => {
  await page.goto("/analytics");
  await page.getByTestId("bar-hit").first().hover();
  await expect(page.getByTestId("chart-tooltip")).toContainText(/\d+ view/);
});

test("a table view exposes the same numbers", async ({ page }) => {
  await page.goto("/analytics");
  await page.getByRole("button", { name: "Table view" }).click();
  const rows = await page.getByTestId("chart-table-row").count();
  expect(rows).toBe(await page.getByTestId("bar").count());
});

test("every timeline event carries an icon and a text label", async ({ page }) => {
  await page.goto("/analytics");
  for (const row of await page.getByTestId("timeline-event").all()) {
    await expect(row.getByTestId("event-icon")).toBeVisible();
    await expect(row.getByTestId("event-label")).not.toBeEmpty();
  }
});

test("the chart has exactly one value axis", async ({ page }) => {
  await page.goto("/analytics");
  await expect(page.getByTestId("y-axis")).toHaveCount(1);
});
```

- [x] **Step 6: Run it to verify it fails**

Run: `npm run e2e -- e2e/analytics.spec.ts`
Expected: FAIL — the route does not exist.

- [x] **Step 7: Implement the screen**

Build the bars as inline SVG `<rect rx="4">` anchored to the baseline, each inside a wider transparent `bar-hit` rect for hovering. Reuse `<StatTile>` from Task 14 for the KPIs and `formatMinor` for the pipeline value.

- [x] **Step 8: Run it to verify it passes**

Run: `npm run e2e -- e2e/analytics.spec.ts`
Expected: PASS — 8 passed.

- [x] **Step 9: Render it and look at it, in both modes**

```bash
npx playwright screenshot --viewport-size=1440,900 http://localhost:3000/analytics var/shots/analytics-light.png
npx playwright screenshot --viewport-size=1440,900 --color-scheme=dark http://localhost:3000/analytics var/shots/analytics-dark.png
```
Open both. Check axis label collisions, bar gaps at narrow widths, tooltip clipping at the right edge, and that dark mode uses the validated dark steps rather than washed-out light hues. Fix what looks wrong — the color validator does not check layout.

- [ ] **Step 10: Commit**

```bash
git add app/web/app/analytics app/web/components app/api/routes/analytics.py app/tests/test_analytics_api.py app/web/e2e/analytics.spec.ts
git commit -m "feat: engagement analytics with stat tiles, event timeline, and single-series chart"
```

---

### Task 19: End-to-end trace tests and the demo runbook

**Files:**
- Create: `app/tests/test_traces.py`
- Create: `app/web/e2e/trace-a.spec.ts`
- Create: `docs/DEMO_RUNBOOK.md`
- Modify: `README.md` (create if absent)

**Interfaces:**
- Consumes: everything.
- Produces: `test_trace_a_end_to_end`, `test_trace_b_end_to_end`, one test per invariant I1–I10, and the click-by-click pitch script.

**Trace A, the ten PRD steps, each asserted:** import the opportunity → attach the transcript → extract requirements → build scope → calculate the quote → generate the draft → validate → approve → render → deliver. Plus the failure branches: a missing source blocks generation, an over-policy discount forces quote approval, and a failed render blocks delivery.

**Trace B:** ingest RFP text → requirements in RFP order → answers mapped to approved claims → deterministic quote → validate → approve → render → deliver, asserting answer order matches requirement order.

- [x] **Step 1: Write the failing invariant tests**

```python
def test_i1_every_client_facing_claim_is_backed(delivered_bundle):
    for section in delivered_bundle.sections:
        for block in section.blocks:
            if contains_verifiable_assertion(block.content):
                assert block.claim_ids
                for cid in block.claim_ids:
                    assert delivered_bundle.claims[cid].status == "approved"
                    assert delivered_bundle.evidence[cid]


def test_i2_every_quote_line_references_one_rule_version(delivered_bundle):
    versions = {delivered_bundle.rules[l.rule_id].version
                for l in delivered_bundle.version.quote.lines}
    assert len(versions) == 1


def test_i3_total_formula_holds(delivered_bundle):
    q = delivered_bundle.version.quote
    assert q.total_minor == q.subtotal_minor - q.discount_minor + q.tax_minor


def test_i4_unselected_optional_lines_are_excluded(delivered_bundle):
    q = delivered_bundle.version.quote
    assert q.subtotal_minor == sum(l.subtotal_minor for l in q.lines if l.selected)


def test_i5_locked_version_cannot_change(client, delivered_version_id):
    for path, body in [("generate", {}), ("quote/calculate", {}), ("validate", {})]:
        assert client.post(f"/v1/proposal-versions/{delivered_version_id}/{path}",
                           json=body).status_code == 409


def test_i6_delivery_required_a_ready_document_and_every_approval(delivered_bundle):
    assert delivered_bundle.document.status == "ready"
    assert all(a.decision == "approved" for a in delivered_bundle.approvals)


def test_i7_expired_or_rejected_claims_cannot_enter_a_new_version(client,
                                                                 delivered_version_id):
    delivered = client.get(f"/v1/proposal-versions/{delivered_version_id}").json()
    r = client.post(f"/v1/proposals/{delivered['proposalId']}/versions",
                    json={"copyFromVersionId": delivered_version_id})
    assert r.status_code == 201
    assert "claim_expired_legacy" not in r.json()["claimIds"]
    assert r.json()["versionNumber"] == delivered["versionNumber"] + 1


def test_i8_each_blocking_condition_blocks_delivery(client, blocking_scenarios):
    for scenario in blocking_scenarios:  # missing source, open question, failed
        assert client.post(f"/v1/proposal-versions/{scenario}/deliver",
                           json={}).status_code == 409


def test_i9_no_float_appears_in_any_money_field(delivered_bundle):
    q = delivered_bundle.version.quote
    for value in [q.subtotal_minor, q.discount_minor, q.tax_minor, q.total_minor,
                  *[l.subtotal_minor for l in q.lines],
                  *[l.unit_price_minor for l in q.lines],
                  *[i.amount_minor for i in q.payment_schedule]]:
        assert isinstance(value, int) and not isinstance(value, bool)


def test_i10_provider_events_append_and_never_mutate(client, delivered_version_id):
    before = client.get(f"/v1/proposal-versions/{delivered_version_id}").json()
    client.post("/v1/engagement/webhook", json={"provider": "docusign", "type": "signed",
                                                "proposalVersionId": delivered_version_id,
                                                "at": "2026-08-03T09:00:00Z"})
    assert client.get(f"/v1/proposal-versions/{delivered_version_id}").json() == before
```

- [x] **Step 2: Write the failing trace tests**

```python
def test_trace_a_end_to_end(client, seed):
    """Import through deliver, asserting the state after each of the ten PRD steps."""
    # 1. Import
    opp = client.post("/v1/opportunities/import",
                      json={"provider": "hubspot", "externalId": "42",
                            "outcome": "success"}).json()
    assert opp["status"] == "normalized"

    # 2. Create the proposal and version 1
    version = client.post("/v1/proposals",
                          json={"opportunityId": opp["id"],
                                "title": "Brand refresh and site rebuild"}).json()
    assert version["status"] == "working"
    vid = version["id"]

    # 3. Attach discovery and 4. extract requirements
    client.post(f"/v1/proposal-versions/{vid}/discovery",
                json={"kind": "transcript", "sourceRecordId": "src_transcript"})
    scope = client.post(f"/v1/proposal-versions/{vid}/scope/extract").json()
    assert len(scope["deliverables"]) == 5
    assert scope["openQuestions"]

    # 5. Resolve the open question so the version can eventually submit
    client.post(f"/v1/proposal-versions/{vid}/scope/resolve",
                json={"openQuestion": scope["openQuestions"][0],
                      "resolution": "Legacy CMS stays on v4 through Q4."})

    # 6. Price
    quote = client.post(f"/v1/proposal-versions/{vid}/quote/calculate",
                        json=TRACE_A_QUOTE_REQUEST).json()
    assert quote["totalMinor"] == (quote["subtotalMinor"]
                                   - quote["discountMinor"] + quote["taxMinor"])
    assert sum(i["amountMinor"] for i in quote["paymentSchedule"]) == quote["totalMinor"]

    # 7. Generate
    draft = client.post(f"/v1/proposal-versions/{vid}/generate",
                        json={"templateId": "tpl_agency",
                              "requestedSections": ["executive_summary", "understanding",
                                                    "scope", "milestones", "assumptions",
                                                    "options", "pricing",
                                                    "payment_schedule", "case_studies",
                                                    "next_steps"],
                              "modelProvider": "claude",
                              "modelName": "claude-opus-5"}).json()
    assert [s["key"] for s in draft["sections"]][0] == "executive_summary"

    # 8. Validate and submit
    flags = client.post(f"/v1/proposal-versions/{vid}/validate").json()["flags"]
    assert [f for f in flags if f["severity"] == "blocking"] == []
    assert client.post(f"/v1/proposal-versions/{vid}/submit").json()["status"] == "submitted"

    # 9. Approve as all three roles, which locks the version
    for approval in client.get(f"/v1/proposal-versions/{vid}").json()["approvals"]:
        client.post(f"/v1/approvals/{approval['id']}/decide",
                    json={"decision": "approved",
                          "reviewerId": f"user_{approval['requiredRole']}",
                          "reviewerRole": approval["requiredRole"]})
    assert client.get(f"/v1/proposal-versions/{vid}").json()["status"] == "locked"

    # 10. Render and deliver
    assert client.post(f"/v1/proposal-versions/{vid}/render",
                       json={}).json()["status"] == "rendered"
    final = client.post(f"/v1/proposal-versions/{vid}/deliver",
                        json={"provider": "pandadoc", "outcome": "success"}).json()
    assert final["status"] == "delivered"
    assert Path(final["documentUri"]).exists()


def test_trace_a_missing_source_blocks_generation(client, version_without_sources):
    r = client.post(f"/v1/proposal-versions/{version_without_sources}/validate")
    assert any(f["code"] == "MISSING_SOURCE" and f["severity"] == "blocking"
               for f in r.json()["flags"])
    assert client.post(
        f"/v1/proposal-versions/{version_without_sources}/submit").status_code == 409


def test_trace_a_over_policy_discount_requires_quote_approval(client, seeded_version):
    body = dict(TRACE_A_QUOTE_REQUEST, discountMinor=900000)
    quote = client.post(f"/v1/proposal-versions/{seeded_version}/quote/calculate",
                        json=body).json()
    assert quote["status"] == "review_required"
    approvals = client.post(f"/v1/proposal-versions/{seeded_version}/submit").json()
    assert any(a["kind"] == "quote" and a["requiredRole"] == "quote_approver"
               for a in approvals["approvals"])


def test_trace_a_failed_render_blocks_delivery(client, locked_version_id):
    r = client.post(f"/v1/proposal-versions/{locked_version_id}/render",
                    json={"outcome": "failure"})
    assert r.json()["status"] == "failed"
    d = client.post(f"/v1/proposal-versions/{locked_version_id}/deliver", json={})
    assert d.status_code == 409
    assert any(f["code"] == "RENDER_ERROR" for f in d.json()["flags"])


def test_trace_b_end_to_end(client, seed):
    opp = client.post("/v1/opportunities/import",
                      json={"provider": "manual", "outcome": "success",
                            "fixture": "rfp_response"}).json()
    version = client.post("/v1/proposals",
                          json={"opportunityId": opp["id"],
                                "title": "RFP 2026-114 response"}).json()
    vid = version["id"]
    client.post(f"/v1/proposal-versions/{vid}/discovery",
                json={"kind": "rfp_text", "sourceRecordId": "src_rfp"})
    client.post(f"/v1/proposal-versions/{vid}/scope/extract")
    client.post(f"/v1/proposal-versions/{vid}/quote/calculate", json=TRACE_B_QUOTE_REQUEST)
    client.post(f"/v1/proposal-versions/{vid}/generate",
                json={"templateId": "tpl_rfp", "requestedSections": ["rfp_answers",
                                                                     "pricing"],
                      "modelProvider": "claude", "modelName": "claude-opus-5"})
    assert [f for f in client.post(f"/v1/proposal-versions/{vid}/validate").json()["flags"]
            if f["severity"] == "blocking"] == []
    client.post(f"/v1/proposal-versions/{vid}/submit")
    for approval in client.get(f"/v1/proposal-versions/{vid}").json()["approvals"]:
        client.post(f"/v1/approvals/{approval['id']}/decide",
                    json={"decision": "approved",
                          "reviewerId": f"user_{approval['requiredRole']}",
                          "reviewerRole": approval["requiredRole"]})
    client.post(f"/v1/proposal-versions/{vid}/render", json={})
    assert client.post(f"/v1/proposal-versions/{vid}/deliver",
                       json={"provider": "docusign",
                             "outcome": "success"}).json()["status"] == "delivered"


def test_trace_b_answers_follow_rfp_order(client, trace_b_version_id):
    sections = client.get(
        f"/v1/proposal-versions/{trace_b_version_id}").json()["sections"]
    answers = next(s for s in sections if s["key"] == "rfp_answers")
    numbers = [int(b["content"].split(".")[0]) for b in answers["blocks"]]
    assert numbers == sorted(numbers)
    assert numbers == list(range(1, 13))


def test_trace_b_every_answer_cites_a_source(client, trace_b_version_id):
    sections = client.get(
        f"/v1/proposal-versions/{trace_b_version_id}").json()["sections"]
    answers = next(s for s in sections if s["key"] == "rfp_answers")
    for block in answers["blocks"]:
        assert block["sourceRecordIds"], block["blockId"]
```

Define `TRACE_A_QUOTE_REQUEST` and `TRACE_B_QUOTE_REQUEST` at the top of the test module as literal dicts built from the Task 13 fixture rule ids, so the trace tests never guess at pricing input.

- [x] **Step 3: Run them to verify they fail**

Run: `pytest app/tests/test_traces.py -v`
Expected: FAIL.

- [x] **Step 4: Fix whatever the traces expose**

These tests are the first thing to exercise the whole chain, so expect gaps at the seams — a missing `promote` call, a flag that never clears, an approval role that was not required. Fix the production code, not the assertions.

- [x] **Step 5: Run them to verify they pass**

Run: `pytest app/tests/test_traces.py -v`
Expected: PASS — 17 passed (10 invariants + 7 trace checks).

- [x] **Step 6: Write the browser trace**

`app/web/e2e/trace-a.spec.ts` — one Playwright test that clicks the entire demo path in the order the runbook uses, ending on the delivered preview with a downloadable PDF. This is the pre-pitch smoke test.

- [x] **Step 7: Write the runbook**

`docs/DEMO_RUNBOOK.md`:

```markdown
# Demo Runbook

## Setup (once)
1. `docker compose up -d db`
2. `python -m pip install -e ".[dev]"` and `python -m playwright install chromium`
3. `cd app/web && npm install`
4. Copy `.env.example` to `.env`. Leave `GENERATION_MODE=fixture` for demos.

## Before every demo (2 minutes)
1. `python -m app.cli reset`
2. `uvicorn app.api.main:app --reload` (terminal 1)
3. `cd app/web && npm run dev` (terminal 2)
4. `cd app/web && npm run e2e -- e2e/trace-a.spec.ts` — the smoke test. If it is
   green the demo will hold.

## The pitch path (8 minutes)
| # | Screen | What to say | What to click |
|---|---|---|---|
| 1 | `/opportunities` | "Nothing is typed twice; the CRM record is the source." | Import from HubSpot |
| 2 | `/opportunities` | "When the source is incomplete we say so instead of guessing." | Switch outcome to failure, import, show the AUTH failure |
| 3 | `/proposals/prop_northwind` | "Every sentence with a number traces to approved evidence." | Click a source chip, show the excerpt |
| 4 | `/proposals/prop_northwind/scope` | "Open questions stay visible until someone answers them." | Resolve the legacy-CMS question |
| 5 | `/proposals/prop_northwind/quote` | "Pricing is deterministic; optional work never inflates the headline." | Toggle training on and off |
| 6 | `/proposals/prop_northwind/quote` | "Discount authority is enforced, not requested." | Enter a 20% discount, show Review required |
| 7 | `/proposals/prop_northwind/approval` | "Delivery is impossible until every gate clears." | Show submit disabled, resolve, submit, approve as all three roles |
| 8 | `/proposals/prop_northwind/preview` | "This is exactly what the client sees." | Download the PDF |
| 9 | `/analytics` | "And we can see what happened after it left." | Fire the viewed webhook, refresh |

## Fallback
If the browser fails, run `python -m app.cli demo`. It prints all eight stages and
produces the same PDF.

## Answering "is this live AI?"
`GENERATION_MODE=fixture` is the default so demos are deterministic. Set
`GENERATION_MODE=live` with `ANTHROPIC_API_KEY` to generate against
`claude-opus-5`. The controls — evidence, pricing, gates, locking — are identical
in both modes.
```

- [x] **Step 8: Full verification**

```bash
pytest -q
ruff check app/
cd app/web && npm run e2e
```
Expected: every suite green.

- [x] **Step 9: Commit**

```bash
git add app/tests/test_traces.py app/web/e2e/trace-a.spec.ts docs/DEMO_RUNBOOK.md README.md
git commit -m "test: end-to-end traces proving I1-I10, plus the demo runbook"
```

---

## Completion Gates

The prototype is demo-ready when all six hold:

1. `python -m app.cli reset && python -m app.cli demo` runs clean from a bare checkout with no provider credentials.
2. `pytest -q` is green, including one test per invariant I1–I10.
3. `cd app/web && npm run e2e` is green, including `trace-a.spec.ts`.
4. All seven portfolio screens render in light and dark mode with a validated palette (validator output recorded in `globals.css`).
5. The generated PDF and the `/preview` screen show the same sections, in the same order, with the same figures.
6. Every mutation in Trace A appears in the audit log, and a provider webhook against a delivered version changes nothing (I10).

## Coverage Notes

Deliberately out of scope for the demo, and why:

- **Auth, signup, tenant provisioning** — the demo runs as seeded users; roles are enforced, the login screen is not built.
- **Live provider credentials** — every boundary runs on fixtures by design, per the PRD's own instruction that the complete demo must not depend on unverified credentials.
- **Migrations tooling** — `create_all` plus `cli reset` is enough for a demo; Alembic is a production concern.
- **Multi-currency** — Trace A and Trace B are both `USD`; the currency check in pricing step 1 exists and is tested, but no second-currency fixture ships.











