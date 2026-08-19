"""Render and deliver locked proposal versions."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.adapters.base import AdapterFailure
from app.adapters.storage import LocalStorage
from app.api import deps
from app.api.utils import dump, flag, flags_response, not_found, version_payload
from app.domain.audit import record_event
from app.domain.schemas import Document
from app.domain.workflow import TransitionError, assert_deliverable
from app.persistence.repositories import (
    ApprovalRepo,
    ClaimRepo,
    DocumentRepo,
    EvidenceRepo,
    OpportunityRepo,
    ProposalRepo,
    SectionRepo,
    VersionRepo,
)

router = APIRouter()


@router.get("/documents/{document_id}/download")
def download(document_id: str, session: Session = Depends(deps.db)):
    document = DocumentRepo(session).find(document_id)
    if document is None or document.status != "ready":
        return not_found("document", document_id)
    try:
        content = LocalStorage().get(f"{document.proposal_version_id}.pdf")
    except (FileNotFoundError, ValueError):
        return not_found("document", document_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{document.id}.pdf"'},
    )


def _render_inputs(session, version):
    claims = ClaimRepo(session).list()
    return (
        SectionRepo(session).list_for_version(version.id),
        {claim.id: claim for claim in claims},
        EvidenceRepo(session).by_claim([claim.id for claim in claims]),
    )


@router.post("/proposal-versions/{version_id}/render")
def render(
    version_id: str,
    body: dict | None = None,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
    renderer=Depends(deps.render_adapter),
):
    body = body or {}
    version = VersionRepo(session).find(version_id)
    if version is None:
        return not_found("proposal version", version_id)
    if version.status != "locked":
        return flags_response([flag("RENDER_ERROR", f"version {version_id} is not locked", [version_id])])
    proposal = ProposalRepo(session).find(version.proposal_id)
    opportunity = OpportunityRepo(session).find(proposal.opportunity_id) if proposal else None
    sections, claims, evidence = _render_inputs(session, version)
    if body.get("outcome") == "failure":
        result = AdapterFailure(
            code="TEMPORARY", provider="manual",
            message="the requested render fixture failed", retryable=False,
        )
    else:
        result = renderer.render(
            version, sections, claims, evidence,
            account_name=opportunity.account_name if opportunity else "",
        )
    documents = DocumentRepo(session)
    if isinstance(result, AdapterFailure):
        failed = Document(
            id=f"doc-{version.id}", proposal_version_id=version.id, status="failed",
            content_type="application/pdf", created_at=clock,
        )
        if documents.find(failed.id):
            documents.update(failed)
        else:
            documents.add(failed)
        record_event(
            session, workspace_id="workspace-demo", actor_type=actor["type"],
            actor_id=actor["id"], action="rendered", entity_type="document",
            entity_id=version_id, after_hash=result.code, created_at=clock,
        )
        return {"status": "failed", "document": dump(failed), "flags": [dump(flag("RENDER_ERROR", result.message, [version.id]))]}
    document = Document(
        id=result.get("documentId", f"doc-{version.id}"),
        proposal_version_id=version.id, status="ready", content_type="application/pdf",
        storage_uri=result.get("uri"), content_hash=result.get("contentHash"),
        created_at=clock, ready_at=clock,
    )
    if documents.find(document.id):
        documents.update(document)
    else:
        documents.add(document)
    try:
        VersionRepo(session).promote(version, "rendered")
    except TransitionError as exc:
        return flags_response([flag("RENDER_ERROR", str(exc), [version_id])])
    record_event(
        session, workspace_id="workspace-demo", actor_type=actor["type"],
        actor_id=actor["id"], action="rendered", entity_type="document",
        entity_id=version_id, after_hash=document.content_hash, created_at=clock,
    )
    return {"status": "rendered", "document": dump(document), "documentUri": document.storage_uri}


@router.post("/proposal-versions/{version_id}/deliver")
def deliver(
    version_id: str,
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    version = VersionRepo(session).find(version_id)
    if version is None:
        return not_found("proposal version", version_id)
    documents = DocumentRepo(session).list(proposal_version_id=version_id)
    document = documents[-1] if documents else None
    approvals = ApprovalRepo(session).list(proposal_version_id=version_id)
    try:
        assert_deliverable(version, document.status if document else "missing", approvals)
    except TransitionError as exc:
        return flags_response([flag("RENDER_ERROR", str(exc), [version_id])])
    try:
        adapter = get_adapter(body.get("provider", "manual"))
    except ValueError as exc:
        return flags_response([flag("SCHEMA_ERROR", str(exc), [version_id])], 422)
    result = adapter.execute({**body, "documentId": document.id})
    if isinstance(result, AdapterFailure):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content=dump(result))
    try:
        VersionRepo(session).promote(version, "delivered")
    except TransitionError as exc:
        return flags_response([flag("RENDER_ERROR", str(exc), [version_id])])
    record_event(
        session, workspace_id="workspace-demo", actor_type=actor["type"],
        actor_id=actor["id"], action="delivered", entity_type="document",
        entity_id=version_id, after_hash=document.content_hash, created_at=clock,
    )
    return version_payload(session, VersionRepo(session).find(version_id)) | {
        "status": "delivered", "documentUri": document.storage_uri,
    }
