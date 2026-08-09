"""Opportunity import and normalization endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.adapters.base import AdapterFailure
from app.api import deps
from app.api.utils import dump, new_id
from app.domain.audit import record_event
from app.domain.schemas import Opportunity, SourceRecord
from app.persistence.repositories import OpportunityRepo, SourceRecordRepo

router = APIRouter()


def _source_type(kind: str) -> str:
    return kind if kind in {"crm", "discovery", "content", "rfp", "manual"} else "manual"


@router.post("/opportunities/import", status_code=201)
def import_opportunity(
    body: dict,
    session: Session = Depends(deps.db),
    clock: str = Depends(deps.now),
    actor: dict = Depends(deps.current_actor),
):
    provider = body.get("provider", "manual")
    try:
        adapter = get_adapter(provider)
    except ValueError:
        from app.api.utils import flag, flags_response

        return flags_response([flag("SCHEMA_ERROR", f"unknown provider {provider}", [])], 422)

    result = adapter.execute(body)
    if isinstance(result, AdapterFailure):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content=dump(result))

    source_repo = SourceRecordRepo(session)
    source_ids: list[str] = []
    for raw in result.get("sourceRecords", []):
        source_id = raw.get("id") or new_id("src")
        source_ids.append(source_id)
        source = SourceRecord(
            id=source_id,
            provider=provider,
            external_id=raw.get("externalId"),
            title=raw.get("label") or raw.get("title") or source_id,
            uri=raw.get("uri"),
            retrieved_at=raw.get("capturedAt", clock),
            content_hash=raw.get("contentHash", f"fixture-{source_id}"),
            excerpt=raw.get("excerpt"),
            source_type=_source_type(raw.get("kind", "manual")),
            approved_for_generation=True,
        )
        if source_repo.find(source_id):
            source_repo.update(source)
        else:
            source_repo.add(source)

    external_id = body.get("externalId", result.get("externalId"))
    account_name = body.get("accountName", result.get("accountName", ""))
    title = body.get("title", result.get("title", ""))
    required = [
        field for field, value in (("accountName", account_name), ("title", title))
        if not str(value or "").strip()
    ]
    opportunity_id = body.get("opportunityId") or (
        f"opp-{provider}-{external_id}" if external_id else new_id("opp")
    )
    opportunity = Opportunity(
        id=opportunity_id,
        external_provider=provider,
        external_id=external_id,
        account_name=account_name or "",
        contact_name=body.get("contactName", result.get("contactName")),
        title=title or "",
        currency=body.get("currency", result.get("currency", "USD")),
        status="needs_attention" if required else "normalized",
        source_record_ids=source_ids,
        required_field_errors=required,
        imported_at=clock,
    )
    opportunities = OpportunityRepo(session)
    if opportunities.find(opportunity.id):
        opportunities.update(opportunity)
    else:
        opportunities.add(opportunity)
    record_event(
        session,
        workspace_id="workspace-demo",
        actor_type=actor["type"],
        actor_id=actor["id"],
        action="imported",
        entity_type="opportunity",
        entity_id=opportunity.id,
        after_hash=f"{opportunity.id}:{opportunity.status}",
        created_at=clock,
    )
    return dump(opportunity)
