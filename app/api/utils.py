"""Small HTTP helpers; business rules stay in ``app.domain``."""

from uuid import uuid4

from fastapi.responses import JSONResponse

from app.domain.schemas import ValidationFlag
from app.persistence.repositories import (
    ApprovalRepo,
    DocumentRepo,
    OpportunityRepo,
    ProposalRepo,
    VersionRepo,
)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"


def dump(value):
    return value.model_dump(by_alias=True) if hasattr(value, "model_dump") else value


def flag(
    code: str,
    message: str,
    related_ids: list[str],
    severity: str = "blocking",
) -> ValidationFlag:
    return ValidationFlag(
        code=code, severity=severity, message=message, related_ids=related_ids
    )


def flags_response(flags: list[ValidationFlag], status_code: int = 409):
    return JSONResponse(
        status_code=status_code,
        content={"flags": [item.model_dump(by_alias=True) for item in flags]},
    )


def not_found(entity: str, entity_id: str):
    return flags_response(
        [flag("SCHEMA_ERROR", f"{entity} {entity_id} was not found", [entity_id])],
        status_code=404,
    )


def version_context(session, version_id: str):
    version = VersionRepo(session).find(version_id)
    if version is None:
        return None
    proposal = ProposalRepo(session).find(version.proposal_id)
    if proposal is None:
        return None
    opportunity = OpportunityRepo(session).find(proposal.opportunity_id)
    return version, proposal, opportunity


def version_payload(session, version):
    approvals = ApprovalRepo(session).list(proposal_version_id=version.id)
    document = DocumentRepo(session).list(proposal_version_id=version.id)
    payload = dump(version)
    payload["approvals"] = [dump(item) for item in approvals]
    payload["document"] = dump(document[-1]) if document else None
    return payload
