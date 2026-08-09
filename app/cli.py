"""Deterministic seed, reset, and terminal demo operations."""

from dataclasses import dataclass
import json
from pathlib import Path
import os

import typer

from app.api.main import create_app
from app.domain.pricing import calculate_quote
from app.domain.schemas import (
    Claim,
    DiscoveryInput,
    DiscountPolicy,
    EvidenceLink,
    Opportunity,
    PricingRule,
    Proposal,
    ProposalVersion,
    Requirement,
    Scope,
    SourceRecord,
)
from app.persistence.models import Base, create_all
from app.persistence.repositories import (
    ClaimRepo,
    DiscoveryRepo,
    DiscountPolicyRepo,
    EvidenceRepo,
    OpportunityRepo,
    PricingRuleRepo,
    ProposalRepo,
    RequirementRepo,
    SourceRecordRepo,
    VersionRepo,
)
from app.persistence.session import get_engine, session_scope

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
SEED_NOW = "2026-08-01T09:30:00Z"


@dataclass(frozen=True)
class SeedResult:
    opportunity_ids: list[str]
    proposal_ids: list[str]
    version_ids: list[str]
    claim_ids: list[str]
    rule_ids: list[str]


def _load(name: str):
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _upsert(repo, value) -> None:
    if repo.find(value.id):
        repo.update(value)
    else:
        repo.add(value)


def _seed_sources(session, *fixtures: dict) -> None:
    repo = SourceRecordRepo(session)
    for fixture in fixtures:
        for raw in fixture["sourceRecords"]:
            source = SourceRecord(
                id=raw["id"],
                provider=raw["provider"],
                external_id=raw.get("externalId"),
                title=raw["title"],
                uri=raw.get("uri"),
                retrieved_at=raw.get("capturedAt", SEED_NOW),
                content_hash=raw.get("contentHash", f"fixture-{raw['id']}"),
                excerpt=raw.get("excerpt"),
                source_type=raw["sourceType"],
                approved_for_generation=True,
            )
            _upsert(repo, source)


def _seed_trace(session, fixture: dict, *, proposal_id: str, version_id: str) -> None:
    opportunity = Opportunity.model_validate(fixture["opportunity"])
    _upsert(OpportunityRepo(session), opportunity)

    discovery = DiscoveryInput.model_validate(fixture["discovery"])
    _upsert(DiscoveryRepo(session), discovery)

    requirements = RequirementRepo(session)
    for raw in fixture["requirements"]:
        requirement = Requirement.model_validate(raw)
        if requirements.find(requirement.id):
            requirements.update(requirement)
        else:
            requirements.add_for_opportunity(opportunity.id, requirement)

    scope = Scope.model_validate(fixture["scope"])
    proposal = Proposal(
        id=proposal_id,
        opportunity_id=opportunity.id,
        status="assembling",
        title=opportunity.title,
        currency=opportunity.currency,
        created_at=SEED_NOW,
    )
    _upsert(ProposalRepo(session), proposal)

    version_repo = VersionRepo(session)
    existing = version_repo.find(version_id)
    if existing is None:
        version_repo.add(ProposalVersion(
            id=version_id,
            proposal_id=proposal_id,
            version_number=1,
            status="working",
            title=opportunity.title,
            scope=scope,
            quote=calculate_quote([], {}, opportunity.currency, calculated_at=SEED_NOW),
            claim_ids=[],
            source_record_ids=opportunity.source_record_ids,
            created_at=SEED_NOW,
        ))


def seed_all(session) -> SeedResult:
    """Upsert both traces and shared claims/rules into an open session."""
    agency = _load("agency_discovery.json")
    rfp = _load("rfp_response.json")
    _seed_sources(session, agency, rfp)
    _seed_trace(session, agency, proposal_id="proposal_northwind", version_id="version_northwind")
    _seed_trace(session, rfp, proposal_id="proposal_rfp_response", version_id="version_rfp_response")

    claim_repo = ClaimRepo(session)
    evidence_repo = EvidenceRepo(session)
    claim_ids: list[str] = []
    for raw in _load("claims.json"):
        claim = Claim.model_validate({key: value for key, value in raw.items() if key != "evidence"})
        _upsert(claim_repo, claim)
        claim_ids.append(claim.id)
        for index, evidence_raw in enumerate(raw.get("evidence", []), start=1):
            evidence = EvidenceLink.model_validate({"claimId": claim.id, **evidence_raw})
            evidence_id = f"evidence-{claim.id}-{index}"
            if not evidence_repo.find(evidence_id):
                evidence_repo.add_link(evidence_id, evidence)

    pricing = _load("pricing_rules.json")
    _upsert(DiscountPolicyRepo(session), DiscountPolicy.model_validate(pricing["discountPolicy"]))
    rule_repo = PricingRuleRepo(session)
    rule_ids: list[str] = []
    for raw in pricing["rules"]:
        rule = PricingRule.model_validate(raw)
        _upsert(rule_repo, rule)
        rule_ids.append(rule.id)

    return SeedResult(
        opportunity_ids=["opp_northwind", "opp_rfp_response"],
        proposal_ids=["proposal_northwind", "proposal_rfp_response"],
        version_ids=["version_northwind", "version_rfp_response"],
        claim_ids=claim_ids,
        rule_ids=rule_ids,
    )


app_cli = typer.Typer(help="Demo operations for the proposal system.")


def _get_database():
    engine = get_engine()
    create_all(engine)
    return engine


@app_cli.command()
def seed():
    """Load Trace A and Trace B fixtures into the database."""
    engine = _get_database()
    with session_scope(engine) as session:
        result = seed_all(session)
    typer.echo(
        f"Seeded {len(result.opportunity_ids)} opportunities, "
        f"{len(result.version_ids)} versions, {len(result.claim_ids)} claims, "
        f"and {len(result.rule_ids)} pricing rules."
    )


@app_cli.command()
def demo():
    """Run Trace A end to end and print each gate as it passes."""
    os.environ.setdefault("STORAGE_DIR", "var/storage")
    engine = _get_database()
    with session_scope(engine) as session:
        seed_all(session)

    from fastapi.testclient import TestClient

    client_app = create_app(engine=engine)
    version_id = "version_northwind"
    with TestClient(client_app) as client:
        typer.echo("Capture    [OK] Trace A opportunity loaded")
        typer.echo("Ground     [OK] discovery, requirements, claims, and sources ready")
        resolved = client.post(
            f"/v1/proposal-versions/{version_id}/scope/resolve",
            json={"openQuestion": "req_legacy_cms", "resolution": "CMS metadata is available through the supported export."},
        )
        if resolved.status_code != 200:
            raise typer.BadParameter(resolved.text)
        typer.echo("Scope      [OK] open question resolved")

        quoted = client.post(
            f"/v1/proposal-versions/{version_id}/quote/calculate",
            json={"currency": "USD", "discountMinor": 0, "taxMinor": 0, "lines": [{"id": "line_strategy", "label": "Strategy days", "ruleId": "rule_strategy_day", "quantity": "4", "optional": False, "selected": True, "sourceRecordIds": ["src-agency-ratecard"]}, {"id": "line_training", "label": "Training session", "ruleId": "rule_training", "quantity": "1", "optional": True, "selected": False, "sourceRecordIds": ["src-agency-ratecard"]}], "installments": [{"sequence": 1, "label": "Deposit", "amountMinor": 240000, "dueDescription": "On signature"}, {"sequence": 2, "label": "Final", "amountMinor": 240000, "dueDescription": "On delivery"}]},
        )
        if quoted.status_code != 200:
            raise typer.BadParameter(quoted.text)
        typer.echo(f"Price      [OK] {quoted.json()['totalMinor']} minor units calculated")

        generated = client.post(
            f"/v1/proposal-versions/{version_id}/generate",
            json={"templateId": "tmpl-consulting-v1", "requestedSections": ["scope", "case_studies"], "modelProvider": "claude", "modelName": "claude-opus-5"},
        )
        if generated.status_code != 200:
            raise typer.BadParameter(generated.text)
        typer.echo("Draft      [OK] source-linked sections generated")

        validated = client.post(f"/v1/proposal-versions/{version_id}/validate")
        if validated.status_code != 200 or any(item["severity"] == "blocking" for item in validated.json()["flags"]):
            raise typer.BadParameter(validated.text)

        submitted = client.post(f"/v1/proposal-versions/{version_id}/submit")
        if submitted.status_code != 200:
            raise typer.BadParameter(submitted.text)
        typer.echo("Approve    [OK] validation clean; submitted for three role approvals")

        approvals = client.get(f"/v1/proposal-versions/{version_id}").json()["approvals"]
        for approval in approvals:
            decided = client.post(
                f"/v1/approvals/{approval['id']}/decide",
                json={"decision": "approved", "reviewerId": f"user-{approval['requiredRole']}", "reviewerRole": approval["requiredRole"]},
            )
            if decided.status_code != 200:
                raise typer.BadParameter(decided.text)

        rendered = client.post(f"/v1/proposal-versions/{version_id}/render")
        if rendered.status_code != 200:
            raise typer.BadParameter(rendered.text)
        delivered = client.post(f"/v1/proposal-versions/{version_id}/deliver", json={"provider": "pandadoc", "outcome": "success"})
        if delivered.status_code != 200:
            raise typer.BadParameter(delivered.text)
        typer.echo(f"Deliver    [OK] {delivered.json()['status']} - {delivered.json().get('documentUri')}")

        audit = client.get(f"/v1/proposal-versions/{version_id}/audit")
        typer.echo(f"Observe    [OK] {len(audit.json())} audit events recorded")


@app_cli.command()
def reset():
    """Drop and recreate all tables, then seed."""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    create_all(engine)
    with session_scope(engine) as session:
        result = seed_all(session)
    typer.echo(f"Reset complete; seeded {len(result.version_ids)} proposal versions.")


if __name__ == "__main__":
    app_cli()
