"""Proposal version lifecycle, generation, and scope endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.adapters.generation import get_generation_adapter
from app.api import deps
from app.api.utils import (
    dump,
    flag,
    flags_response,
    new_id,
    not_found,
    version_context,
    version_payload,
)
from app.domain.audit import record_event
from app.domain.claims import usable_in_new_version
from app.domain.schemas import (
    ApprovedClaim,
    Approval,
    GenerateDraftRequest,
    Proposal,
    ProposalVersion,
    Quote,
    Scope,
)
from app.domain.workflow import TransitionError, assert_mutable
from app.domain.validation import blocking_flags, validate_version
from app.persistence.repositories import (
    ApprovalRepo,
    ClaimRepo,
    DiscoveryRepo,
    DocumentRepo,
    EvidenceRepo,
    OpportunityRepo,
    ProposalRepo,
    RequirementRepo,
    SectionRepo,
    SourceRecordRepo,
    VersionRepo,
)

router = APIRouter()


def _fixture(name: str) -> dict | None:
    path = Path(__file__).resolve().parents[2] / "fixtures" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _empty_quote(currency: str, clock: str) -> Quote:
    from app.domain.pricing import calculate_quote

    return calculate_quote([], {}, currency, calculated_at=clock)


def _claims(session, claim_ids: list[str] | None = None):
    claims = ClaimRepo(session).list()
    if claim_ids is not None:
        claims = [claim for claim in claims if claim.id in claim_ids]
    evidence = EvidenceRepo(session).by_claim([claim.id for claim in claims])
    return claims, evidence


def _record(session, actor, clock, action, version_id, before=None, after=None):
    return record_event(
        session,
        workspace_id="workspace-demo",
        actor_type=actor["type"],
        actor_id=actor["id"],
        action=action,
        entity_type="proposal",
        entity_id=version_id,
        before_hash=before,
        after_hash=after,
        created_at=clock,
    )


def _validation_inputs(session, version, opportunity):
    sections = SectionRepo(session).list_for_version(version.id)
    claims, evidence = _claims(session)
    rules = {item.id: item for item in __import__(
        "app.persistence.repositories", fromlist=["PricingRuleRepo"]
    ).PricingRuleRepo(session).list()}
    requirements = RequirementRepo(session).list_for_opportunity(opportunity.id)
    approvals = ApprovalRepo(session).list(proposal_version_id=version.id)
    documents = DocumentRepo(session).list(proposal_version_id=version.id)
    document_status = documents[-1].status if documents else "requested"
    return sections, claims, evidence, rules, requirements, approvals, document_status


@router.post("/proposals", status_code=201)
def create_proposal(
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    opportunity_id = body.get("opportunityId")
    opportunity = OpportunityRepo(session).find(opportunity_id)
    if opportunity is None:
        return not_found("opportunity", opportunity_id or "")
    proposal_id = new_id("proposal")
    version_id = new_id("version")
    title = body.get("title") or opportunity.title or "Untitled proposal"
    proposal = Proposal(
        id=proposal_id,
        opportunity_id=opportunity.id,
        status="assembling",
        title=title,
        currency=opportunity.currency,
        created_at=clock,
    )
    version = ProposalVersion(
        id=version_id,
        proposal_id=proposal_id,
        version_number=1,
        status="working",
        title=title,
        scope=Scope(),
        quote=_empty_quote(opportunity.currency, clock),
        created_at=clock,
    )
    ProposalRepo(session).add(proposal)
    VersionRepo(session).add(version)
    _record(session, actor, clock, "edited", version.id, after=version.id)
    return {"proposal": dump(proposal), "version": dump(version)}


@router.get("/proposal-versions/{version_id}")
def get_version(version_id: str, session: Session = Depends(deps.db)):
    version = VersionRepo(session).find(version_id)
    if version is None:
        return not_found("proposal version", version_id)
    return version_payload(session, version) | {
        "sections": [dump(item) for item in SectionRepo(session).list_for_version(version.id)],
    }


@router.get("/proposal-versions/{version_id}/audit")
def get_audit(version_id: str, session: Session = Depends(deps.db)):
    from app.persistence.repositories import AuditRepo

    if VersionRepo(session).find(version_id) is None:
        return not_found("proposal version", version_id)
    return [dump(item) for item in AuditRepo(session).list_for(version_id)]


@router.post("/proposal-versions/{version_id}/discovery")
def attach_discovery(
    version_id: str,
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    context = version_context(session, version_id)
    if context is None:
        return not_found("proposal version", version_id)
    version, _, opportunity = context
    try:
        assert_mutable(version)
    except TransitionError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])])
    source_id = body.get("sourceRecordId")
    source_repo = SourceRecordRepo(session)
    source = source_repo.find(source_id)
    fixture_name = "agency_discovery" if body.get("kind") == "transcript" else "rfp_response" if body.get("kind") == "rfp_text" else None
    fixture = _fixture(fixture_name) if fixture_name else None
    if fixture:
        for raw in fixture.get("requirements", []):
            requirement = __import__("app.domain.schemas", fromlist=["Requirement"]).Requirement.model_validate(raw)
            requirements = RequirementRepo(session)
            if requirements.find(requirement.id) is None:
                requirements.add_for_opportunity(opportunity.id, requirement)
        if source is None and source_id:
            raw = fixture["sourceRecords"][0]
            from app.domain.schemas import SourceRecord

            source = SourceRecord(
                id=source_id, provider=raw["provider"], external_id=raw.get("externalId"),
                title=raw["title"], uri=raw.get("uri"), retrieved_at=raw.get("capturedAt", clock),
                content_hash=raw.get("contentHash", f"fixture-{source_id}"), excerpt=raw.get("excerpt"),
                source_type=raw["sourceType"], approved_for_generation=True,
            )
            source_repo.add(source)
    discovery = __import__("app.domain.schemas", fromlist=["DiscoveryInput"]).DiscoveryInput(
        id=body.get("id") or new_id("discovery"),
        opportunity_id=opportunity.id,
        kind=body.get("kind", "notes"),
        text=body.get("text") or (fixture.get("discovery", {}).get("text") if fixture else None) or (source.excerpt if source else ""),
        source_record_id=source_id,
        extracted_at=clock,
    )
    DiscoveryRepo(session).add(discovery)
    version = version.model_copy(update={
        "source_record_ids": sorted(set(version.source_record_ids + [source_id])),
    })
    VersionRepo(session).update(version)
    _record(session, actor, clock, "edited", version_id)
    return dump(discovery)


@router.post("/proposal-versions/{version_id}/scope/extract")
def extract_scope(
    version_id: str,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    context = version_context(session, version_id)
    if context is None:
        return not_found("proposal version", version_id)
    version, _, opportunity = context
    try:
        assert_mutable(version)
    except TransitionError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])])
    requirements = RequirementRepo(session).list_for_opportunity(opportunity.id)
    fixture = _fixture("agency_discovery") if any(item.id.startswith("req_") for item in requirements) else _fixture("rfp_response") if any(item.id.startswith("rfp_req_") for item in requirements) else None
    if fixture:
        scope = Scope.model_validate(fixture["scope"])
        open_questions = [requirement.id for requirement in requirements if requirement.status == "open_question"]
        scope = scope.model_copy(update={"open_questions": open_questions})
    else:
        deliverables = [
            {
                "id": f"deliverable-{requirement.id}",
                "name": requirement.text,
                "description": requirement.text,
                "quantity": 1,
                "unit": "engagement",
                "sourceRecordIds": requirement.source_record_ids,
            }
            for requirement in requirements
            if requirement.status != "open_question"
        ]
        open_questions = [requirement.id for requirement in requirements if requirement.status == "open_question"]
        scope = version.scope.model_copy(update={
            "deliverables": deliverables,
            "open_questions": open_questions,
        })
    updated = version.model_copy(update={"scope": scope})
    VersionRepo(session).update(updated)
    _record(session, actor, clock, "edited", version_id)
    return dump(scope)


@router.post("/proposal-versions/{version_id}/scope/resolve")
def resolve_scope(
    version_id: str,
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    context = version_context(session, version_id)
    if context is None:
        return not_found("proposal version", version_id)
    version, _, opportunity = context
    try:
        assert_mutable(version)
    except TransitionError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])])
    try:
        assert_mutable(version)
    except TransitionError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])])
    question = body.get("openQuestion", "")
    resolution = body.get("resolution", "")
    requirements = RequirementRepo(session).list_for_opportunity(opportunity.id)
    for requirement in requirements:
        if requirement.id == question or requirement.text == question:
            RequirementRepo(session).update(requirement.model_copy(update={"status": "confirmed"}))
    scope = version.scope.model_copy(update={
        "open_questions": [item for item in version.scope.open_questions if item not in {question, question.strip()}],
    })
    updated = version.model_copy(update={"scope": scope})
    VersionRepo(session).update(updated)
    _record(session, actor, clock, "edited", version_id, after=resolution[:120] or None)
    return dump(scope)


@router.post("/proposal-versions/{version_id}/generate")
def generate(
    version_id: str,
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    context = version_context(session, version_id)
    if context is None:
        return not_found("proposal version", version_id)
    version, _, opportunity = context
    if not version.source_record_ids and not opportunity.source_record_ids:
        return flags_response([flag("MISSING_SOURCE", "a proposal cannot be generated without an approved source record", [version_id])])
    try:
        assert_mutable(version)
    except TransitionError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])])
    claims, evidence = _claims(session)
    approved = [
        ApprovedClaim(**claim.model_dump(), evidence=evidence.get(claim.id, []))
        for claim in claims
        if claim.status == "approved"
    ]
    request = GenerateDraftRequest(
        proposal_version_id=version.id,
        opportunity=opportunity,
        discovery=DiscoveryRepo(session).list(opportunity_id=opportunity.id),
        requirements=RequirementRepo(session).list_for_opportunity(opportunity.id),
        scope=version.scope,
        approved_claims=approved,
        template_id=body.get("templateId", "tmpl-consulting-v1"),
        requested_sections=body.get("requestedSections", ["scope", "case_studies"]),
        model_provider=body.get("modelProvider", "claude"),
        model_name=body.get("modelName", "claude-opus-5"),
    )
    try:
        response = get_generation_adapter().generate(request, now=clock)
    except Exception as exc:  # fixture packaging/configuration errors are reportable
        return flags_response([flag("SCHEMA_ERROR", f"generation failed: {exc}", [version_id])], 502)
    SectionRepo(session).replace_for_version(version_id, response.sections)
    used_claim_ids = sorted({usage.claim_id for usage in response.claims_used})
    source_ids = sorted({source_id for section in response.sections for block in section.blocks for source_id in block.source_record_ids})
    updated = version.model_copy(update={
        "claim_ids": used_claim_ids,
        "source_record_ids": sorted(set(version.source_record_ids + source_ids)),
        "unresolved_flags": [item.code for item in response.unresolved_flags],
    })
    VersionRepo(session).update(updated)
    _record(session, actor, clock, "generated", version_id)
    return dump(response)


@router.post("/proposal-versions/{version_id}/validate")
def validate(
    version_id: str,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    context = version_context(session, version_id)
    if context is None:
        return not_found("proposal version", version_id)
    version, _, opportunity = context
    try:
        assert_mutable(version)
    except TransitionError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])])
    inputs = _validation_inputs(session, version, opportunity)
    sections, claims, evidence, rules, requirements, approvals, document_status = inputs
    flags = validate_version(
        version=version,
        sections=sections,
        claims_by_id={item.id: item for item in claims},
        evidence_by_claim=evidence,
        rules=rules,
        requirements=requirements,
        approvals=approvals,
        document_status=document_status,
        now=clock,
    )
    VersionRepo(session).update(version.model_copy(update={
        "unresolved_flags": [item.code for item in flags if item.severity == "blocking"],
    }))
    _record(session, actor, clock, "validated", version_id)
    return {"flags": [dump(item) for item in flags]}


@router.post("/proposal-versions/{version_id}/submit")
def submit(
    version_id: str,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    context = version_context(session, version_id)
    if context is None:
        return not_found("proposal version", version_id)
    version, _, opportunity = context
    inputs = _validation_inputs(session, version, opportunity)
    sections, claims, evidence, rules, requirements, approvals, document_status = inputs
    flags = validate_version(
        version=version,
        sections=sections,
        claims_by_id={item.id: item for item in claims},
        evidence_by_claim=evidence,
        rules=rules,
        requirements=requirements,
        approvals=approvals,
        document_status=document_status,
        now=clock,
    )
    if not sections:
        flags.append(flag("SCHEMA_ERROR", "a proposal needs generated sections before submission", [version_id]))
    if blocking_flags(flags):
        VersionRepo(session).update(version.model_copy(update={
            "unresolved_flags": [item.code for item in flags if item.severity == "blocking"],
        }))
        return flags_response(flags)
    try:
        VersionRepo(session).promote(version, "submitted")
    except TransitionError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])])
    approvals = []
    for kind, role in (("quote", "quote_approver"), ("proposal", "proposal_approver"), ("claim", "content_editor")):
        approval = Approval(
            id=new_id("approval"), proposal_version_id=version_id, kind=kind,
            required_role=role, decision="pending",
        )
        ApprovalRepo(session).add(approval)
        approvals.append(approval)
    _record(session, actor, clock, "edited", version_id)
    return {"status": "submitted", "approvals": [dump(item) for item in approvals]}


@router.post("/proposals/{proposal_id}/versions", status_code=201)
def copy_version(
    proposal_id: str,
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    proposal = ProposalRepo(session).find(proposal_id)
    source_id = body.get("copyFromVersionId")
    source = VersionRepo(session).find(source_id)
    if proposal is None:
        return not_found("proposal", proposal_id)
    if source is None or source.proposal_id != proposal_id:
        return not_found("proposal version", source_id or "")
    claims, _ = _claims(session)
    copied_ids = [claim.id for claim in claims if usable_in_new_version(claim, clock)]
    version = ProposalVersion(
        id=new_id("version"), proposal_id=proposal_id,
        version_number=VersionRepo(session).next_version_number(proposal_id),
        status="working", title=source.title, scope=source.scope, quote=source.quote,
        claim_ids=copied_ids, source_record_ids=source.source_record_ids,
        created_at=clock,
    )
    VersionRepo(session).add(version)
    _record(session, actor, clock, "edited", version.id, after=version.id)
    return {"proposal": dump(proposal), "version": dump(version), **dump(version)}
