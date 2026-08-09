"""Read-only content and analytics views used by the demo shell."""

from datetime import datetime
from statistics import median

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.api.utils import dump, new_id, not_found
from app.domain.audit import record_event
from app.domain.schemas import EngagementRecord
from app.persistence.repositories import ClaimRepo, EvidenceRepo, VersionRepo
from app.persistence.repositories import EngagementRepo

router = APIRouter()


@router.get("/content/claims")
def list_claims(session: Session = Depends(deps.db)):
    evidence = EvidenceRepo(session).by_claim([claim.id for claim in ClaimRepo(session).list()])
    return [dump(claim) | {"evidence": [dump(item) for item in evidence.get(claim.id, [])]}
            for claim in ClaimRepo(session).list()]


@router.get("/analytics/summary")
def analytics_summary(session: Session = Depends(deps.db)):
    versions = VersionRepo(session).list()
    by_status: dict[str, int] = {}
    for version in versions:
        by_status[version.status] = by_status.get(version.status, 0) + 1
    return {"proposalVersions": len(versions), "byStatus": by_status}


def _day(value: str) -> str:
    return value[:10]


def _cycle_days(sent_at: str, signed_at: str) -> float:
    start = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(signed_at.replace("Z", "+00:00"))
    return round((end - start).total_seconds() / 86400, 1)


@router.get("/analytics/engagement")
def engagement_analytics(session: Session = Depends(deps.db)):
    records = sorted(EngagementRepo(session).list(), key=lambda item: item.at)
    versions = VersionRepo(session).list()
    versions_by_id = {version.id: version for version in versions}
    sent = {item.proposal_version_id for item in records if item.type == "sent"}
    signed = {item.proposal_version_id for item in records if item.type == "signed"}
    cycles = []
    for version_id in sent & signed:
        version_events = [item for item in records if item.proposal_version_id == version_id]
        sent_at = next(item.at for item in version_events if item.type == "sent")
        signed_at = next(item.at for item in version_events if item.type == "signed")
        cycles.append(_cycle_days(sent_at, signed_at))

    views: dict[str, int] = {}
    for item in records:
        if item.type == "viewed":
            views[_day(item.at)] = views.get(_day(item.at), 0) + 1
    events = []
    for item in records:
        version = versions_by_id.get(item.proposal_version_id)
        event = {
            "id": item.id,
            "type": item.type,
            "actor": item.provider,
            "at": item.at,
            "proposalId": version.proposal_id if version else item.proposal_version_id,
        }
        if item.document_id:
            event["documentId"] = item.document_id
        events.append(event)

    pipeline_value = sum(version.quote.total_minor for version in versions
                          if version.status not in {"working", "superseded"})
    return {
        "kpis": [
            {"key": "proposals_sent", "label": "Proposals sent", "value": len(sent), "unit": "proposals"},
            {"key": "win_rate", "label": "Win rate", "value": round(len(signed) / len(sent) * 100, 1) if sent else 0, "unit": "%"},
            {"key": "median_cycle_days", "label": "Median cycle", "value": median(cycles) if cycles else 0, "unit": "days"},
            {"key": "pipeline_value", "label": "Pipeline value", "valueMinor": pipeline_value, "unit": "USD"},
        ],
        "events": events,
        "viewsByDay": [{"day": day, "count": count} for day, count in sorted(views.items())],
    }


@router.post("/engagement/webhook", status_code=201)
def engagement_webhook(
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
):
    version_id = body.get("proposalVersionId")
    version = VersionRepo(session).find(version_id) if version_id else None
    if version is None:
        return not_found("proposal version", version_id or "")
    record = EngagementRecord(
        id=new_id("eng"), proposal_version_id=version_id,
        provider=body.get("provider", "manual"), type=body.get("type", "viewed"),
        document_id=body.get("documentId"), at=body.get("at") or clock,
    )
    EngagementRepo(session).add(record)
    record_event(
        session, workspace_id="workspace-demo", actor_type="provider",
        actor_id=record.provider, action="engagement_received",
        entity_type="proposal", entity_id=version_id,
        after_hash=record.id, created_at=clock,
    )
    return {"engagement": dump(record), "status": "received"}
