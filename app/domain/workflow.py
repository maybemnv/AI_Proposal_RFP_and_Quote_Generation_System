"""State machines, immutability, and delivery preconditions (I5, I6, I8).

The adjacency maps below are the PRD's six state models transcribed literally.
Anything not listed is not a legal transition — including transitions out of a
terminal state, which is how I5 stops a locked version from reopening.

``assert_*`` functions raise or return None. They never return a boolean: a
caller that forgets to check a bool fails open, and every one of these guards a
client-facing invariant.
"""

import hashlib
import json

from app.domain.schemas import Approval, ProposalVersion

TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "opportunity": {
        "imported": {"normalized", "needs_attention"},
        "needs_attention": {"normalized"},
        "normalized": set(),
    },
    "proposal": {
        "assembling": {"draft", "archived"},
        "draft": {"in_review", "archived"},
        "in_review": {"approved", "rejected"},
        "approved": {"delivered", "archived"},
        "rejected": {"draft", "archived"},
        "delivered": {"archived"},
        "archived": set(),
    },
    "proposal_version": {
        "working": {"submitted"},
        "submitted": {"locked", "working"},
        "locked": {"rendered"},
        "rendered": {"delivered"},
        "delivered": set(),
    },
    "content_item": {
        "draft": {"pending_approval"},
        "pending_approval": {"approved", "rejected"},
        "approved": {"expired"},
        "expired": set(),
        "rejected": {"draft"},
    },
    "quote": {
        "calculated": {"review_required", "approved"},
        "review_required": {"approved", "rejected"},
        "approved": {"superseded"},
        "rejected": {"calculated"},
        "superseded": set(),
    },
    "approval": {"pending": {"approved", "rejected"}, "approved": set(), "rejected": set()},
    "document": {
        "requested": {"rendering"},
        "rendering": {"ready", "failed"},
        "ready": set(),
        "failed": {"requested"},
    },
}

IMMUTABLE_STATUSES = {"locked", "rendered", "delivered"}


class TransitionError(ValueError):
    """Raised when a state change or mutation violates the workflow rules."""


def assert_transition(entity: str, current: str, target: str) -> None:
    states = TRANSITIONS.get(entity)
    if states is None:
        raise TransitionError(f"unknown entity {entity!r}")
    if current not in states:
        raise TransitionError(f"{entity}: unknown state {current!r}")
    if target not in states[current]:
        raise TransitionError(f"{entity}: {current} -> {target} is not allowed")


def assert_mutable(version: ProposalVersion) -> None:
    """I5 — a locked version cannot change."""
    if version.status in IMMUTABLE_STATUSES:
        raise TransitionError(f"version {version.id} is locked and cannot be modified")


def content_hash(version: ProposalVersion) -> str:
    """Hash the content, not the bookkeeping.

    ``locked_at`` and ``status`` are excluded so the same content hashes alike
    whether it is being submitted, locked, or replayed from storage — which is
    what lets a later render prove it rendered the version that was approved.
    """
    payload = version.model_dump(by_alias=True, exclude={"locked_at", "status"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def lock_version(version: ProposalVersion, locked_at: str) -> ProposalVersion:
    assert_transition("proposal_version", version.status, "locked")
    return version.model_copy(update={"status": "locked", "locked_at": locked_at})


def assert_deliverable(
    version: ProposalVersion,
    document_status: str,
    approvals: list[Approval],
) -> None:
    """I6 and I8 — a ready document, every required approval, and no blocking flags."""
    if version.unresolved_flags:
        raise TransitionError(f"unresolved flags block delivery: {version.unresolved_flags}")
    if not approvals:
        raise TransitionError("missing approval: no approvals recorded for this version")
    outstanding = [a.id for a in approvals if a.decision != "approved"]
    if outstanding:
        raise TransitionError(f"missing approval: {outstanding}")
    if document_status != "ready":
        raise TransitionError(f"document is {document_status}, not ready")
