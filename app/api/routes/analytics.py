"""Read-only content and analytics views used by the demo shell."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.api.utils import dump
from app.persistence.repositories import ClaimRepo, EvidenceRepo, VersionRepo

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
