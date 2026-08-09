"""Append-only audit trail.

Every mutating operation records who did what to which entity, and the content
hashes before and after. The log is append-only by construction: ``AuditRepo``
has no update or delete path, and ``record_event`` validates the event through
Pydantic *before* touching the session, so a rejected action never leaves a row.

Event ids are derived from the event's own content rather than a random uuid so
seeding the demo twice produces the same ids — replayable fixtures, stable
screenshots. The counter disambiguates events identical in every other field.
"""

import hashlib
from itertools import count
from typing import Any

from sqlalchemy.orm import Session

from app.domain.schemas import AuditEvent
from app.persistence.models import AuditEventRow

_sequence = count()


def _event_id(payload: dict[str, Any]) -> str:
    seed = "|".join(str(payload[k]) for k in sorted(payload))
    seed = f"{seed}|{next(_sequence)}"
    return f"aud-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def record_event(
    session: Session,
    *,
    workspace_id: str,
    actor_type: str,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    before_hash: str | None = None,
    after_hash: str | None = None,
    metadata: dict[str, str] | None = None,
    created_at: str,
) -> AuditEvent:
    """Validate, append, return. Raises ValidationError on an unknown action."""
    fields = {
        "workspace_id": workspace_id,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "metadata": metadata or {},
        "created_at": created_at,
    }
    event = AuditEvent(id=_event_id(fields), **fields)

    session.add(AuditEventRow(
        id=event.id,
        workspace_id=event.workspace_id,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        before_hash=event.before_hash,
        after_hash=event.after_hash,
        event_metadata=event.metadata,
        created_at=event.created_at,
    ))
    return event
