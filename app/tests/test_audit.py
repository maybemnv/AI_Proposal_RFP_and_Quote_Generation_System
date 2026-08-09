import pydantic
import pytest

from app.domain.audit import record_event
from app.persistence.repositories import AuditRepo
from app.persistence.session import session_scope


def test_audit_events_are_append_only(engine):
    with session_scope(engine) as s:
        record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                     action="locked", entity_type="proposal", entity_id="p1",
                     before_hash="a", after_hash="b", metadata={"version": "1"},
                     created_at="2026-08-01T10:00:00Z")
    with session_scope(engine) as s:
        events = AuditRepo(s).list_for("p1")
        assert len(events) == 1
        assert events[0].action == "locked"
        assert events[0].metadata == {"version": "1"}
        with pytest.raises(NotImplementedError, match="append-only"):
            AuditRepo(s).delete("p1")


def test_audit_update_is_also_refused(engine):
    with session_scope(engine) as s:
        event = record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                             action="edited", entity_type="proposal", entity_id="p1",
                             created_at="2026-08-01T10:00:00Z")
    with session_scope(engine) as s, pytest.raises(NotImplementedError, match="append-only"):
        AuditRepo(s).update(event.model_copy(update={"action": "approved"}))


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
        assert event.actor_id is None


def test_unknown_action_is_rejected(engine):
    with session_scope(engine) as s, pytest.raises(pydantic.ValidationError):
        record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                     action="deleted", entity_type="proposal", entity_id="p1",
                     metadata={}, created_at="2026-08-01T12:00:00Z")


def test_rejected_event_writes_no_row(engine):
    """Validation must happen before the row is added, not after."""
    with session_scope(engine) as s:
        with pytest.raises(pydantic.ValidationError):
            record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                         action="deleted", entity_type="proposal", entity_id="p1",
                         created_at="2026-08-01T12:00:00Z")
        s.rollback()
    with session_scope(engine) as s:
        assert AuditRepo(s).list_for("p1") == []


def test_history_is_ordered_oldest_first(engine):
    with session_scope(engine) as s:
        for at, action in [("2026-08-01T12:00:00Z", "locked"),
                           ("2026-08-01T10:00:00Z", "generated"),
                           ("2026-08-01T11:00:00Z", "validated")]:
            record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                         action=action, entity_type="proposal", entity_id="p1",
                         created_at=at)
    with session_scope(engine) as s:
        assert [e.action for e in AuditRepo(s).list_for("p1")] == [
            "generated", "validated", "locked"]


def test_event_ids_are_unique_without_a_caller_supplying_them(engine):
    with session_scope(engine) as s:
        for action in ("generated", "validated", "approved"):
            record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                         action=action, entity_type="proposal", entity_id="p1",
                         created_at="2026-08-01T10:00:00Z")
    with session_scope(engine) as s:
        ids = [e.id for e in AuditRepo(s).list_for("p1")]
        assert len(set(ids)) == 3


def test_workspace_history_spans_entities(engine):
    with session_scope(engine) as s:
        record_event(s, workspace_id="w1", actor_type="user", actor_id="u1",
                     action="generated", entity_type="proposal", entity_id="p1",
                     created_at="2026-08-01T10:00:00Z")
        record_event(s, workspace_id="w1", actor_type="provider", actor_id=None,
                     action="engagement_received", entity_type="document",
                     entity_id="d1", created_at="2026-08-01T11:00:00Z")
    with session_scope(engine) as s:
        assert len(AuditRepo(s).list_for_workspace("w1")) == 2


def test_metadata_defaults_to_empty_dict(engine):
    with session_scope(engine) as s:
        event = record_event(s, workspace_id="w1", actor_type="system", actor_id=None,
                             action="validated", entity_type="proposal", entity_id="p1",
                             created_at="2026-08-01T10:00:00Z")
    assert event.metadata == {}
