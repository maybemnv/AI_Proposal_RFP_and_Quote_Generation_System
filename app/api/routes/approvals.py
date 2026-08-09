"""Role-gated approval decisions."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.api.utils import dump, flag, flags_response, not_found, version_payload
from app.domain.audit import record_event
from app.domain.workflow import TransitionError
from app.persistence.repositories import ApprovalRepo, VersionRepo

router = APIRouter()


@router.post("/approvals/{approval_id}/decide")
def decide(
    approval_id: str,
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    approvals = ApprovalRepo(session)
    approval = approvals.find(approval_id)
    if approval is None:
        return not_found("approval", approval_id)
    if body.get("reviewerRole") != approval.required_role:
        return flags_response([flag(
            "MISSING_APPROVAL",
            f"reviewer role {body.get('reviewerRole')} cannot decide {approval.required_role}",
            [approval_id],
        )], status_code=403)
    decision = body.get("decision", "approved")
    if decision not in {"approved", "rejected"}:
        return flags_response([flag("SCHEMA_ERROR", f"unsupported decision {decision}", [approval_id])], 422)
    updated = approval.model_copy(update={
        "decision": decision, "reviewer_id": body.get("reviewerId") or actor["id"],
        "comment": body.get("comment"), "decided_at": clock,
    })
    approvals.update(updated)
    record_event(
        session, workspace_id="workspace-demo", actor_type=actor["type"],
        actor_id=actor["id"], action="approved" if decision == "approved" else "rejected",
        entity_type="proposal", entity_id=approval.proposal_version_id,
        after_hash=approval_id, created_at=clock,
    )
    version = VersionRepo(session).find(approval.proposal_version_id)
    all_approvals = approvals.list(proposal_version_id=approval.proposal_version_id)
    if decision == "approved" and version and all(item.decision == "approved" for item in all_approvals):
        try:
            locked = version.model_copy(update={"locked_at": clock})
            VersionRepo(session).promote(locked, "locked")
        except TransitionError as exc:
            return flags_response([flag("SCHEMA_ERROR", str(exc), [version.id])])
        record_event(
            session, workspace_id="workspace-demo", actor_type=actor["type"],
            actor_id=actor["id"], action="locked", entity_type="proposal",
            entity_id=version.id, after_hash=version.id, created_at=clock,
        )
    return {"approval": dump(updated), "version": version_payload(session, VersionRepo(session).find(approval.proposal_version_id))}
