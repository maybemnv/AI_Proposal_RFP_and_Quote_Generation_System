import pytest

from app.domain.workflow import (
    TransitionError,
    assert_deliverable,
    assert_mutable,
    assert_transition,
    content_hash,
    lock_version,
)


def test_valid_proposal_version_path():
    for current, target in [("working", "submitted"), ("submitted", "locked"),
                            ("locked", "rendered"), ("rendered", "delivered")]:
        assert assert_transition("proposal_version", current, target) is None


def test_cannot_skip_lock():
    with pytest.raises(TransitionError):
        assert_transition("proposal_version", "submitted", "rendered")


def test_terminal_state_has_no_exit():
    with pytest.raises(TransitionError):
        assert_transition("proposal_version", "delivered", "working")


def test_unknown_entity_is_an_error_not_a_silent_pass():
    with pytest.raises(TransitionError, match="unknown entity"):
        assert_transition("sandwich", "working", "locked")


def test_unknown_state_is_an_error_not_a_silent_pass():
    with pytest.raises(TransitionError):
        assert_transition("proposal_version", "banana", "locked")


def test_working_version_is_mutable(working_version):
    assert assert_mutable(working_version) is None


def test_cannot_reopen_locked_version(locked_version):
    with pytest.raises(TransitionError, match="locked"):
        assert_mutable(locked_version)


def test_rendered_and_delivered_are_also_immutable(locked_version):
    for status in ("rendered", "delivered"):
        with pytest.raises(TransitionError):
            assert_mutable(locked_version.model_copy(update={"status": status}))


def test_locking_sets_status_and_timestamp(working_version):
    submitted = working_version.model_copy(update={"status": "submitted"})
    locked = lock_version(submitted, "2026-08-01T10:00:00Z")
    assert locked.status == "locked"
    assert locked.locked_at == "2026-08-01T10:00:00Z"


def test_locking_a_working_version_is_rejected(working_version):
    with pytest.raises(TransitionError):
        lock_version(working_version, "2026-08-01T10:00:00Z")


def test_content_hash_ignores_lock_time_but_not_content(working_version):
    submitted = working_version.model_copy(update={"status": "submitted"})
    early = lock_version(submitted, "2026-08-01T10:00:00Z")
    late = lock_version(submitted, "2026-09-15T23:59:00Z")
    assert content_hash(early) == content_hash(late)

    edited = early.model_copy(update={"title": "A different engagement"})
    assert content_hash(edited) != content_hash(early)


def test_delivery_blocked_without_ready_document(locked_version, approvals_all_approved):
    with pytest.raises(TransitionError, match="document"):
        assert_deliverable(locked_version, "rendering", approvals_all_approved)


def test_delivery_blocked_by_pending_approval(locked_version, approvals_one_pending):
    with pytest.raises(TransitionError, match="approval"):
        assert_deliverable(locked_version, "ready", approvals_one_pending)


def test_delivery_blocked_by_rejected_approval(locked_version, approvals_all_approved):
    rejected = [approvals_all_approved[0],
                approvals_all_approved[1].model_copy(update={"decision": "rejected"})]
    with pytest.raises(TransitionError, match="approval"):
        assert_deliverable(locked_version, "ready", rejected)


def test_delivery_blocked_when_no_approvals_exist_at_all(locked_version):
    with pytest.raises(TransitionError, match="approval"):
        assert_deliverable(locked_version, "ready", [])


def test_delivery_blocked_by_unresolved_flag(locked_version_with_flag, approvals_all_approved):
    with pytest.raises(TransitionError, match="unresolved"):
        assert_deliverable(locked_version_with_flag, "ready", approvals_all_approved)


def test_delivery_allowed_when_all_conditions_met(locked_version, approvals_all_approved):
    assert assert_deliverable(locked_version, "ready", approvals_all_approved) is None
