"""Row types mirroring the domain aggregates.

Nested aggregates (scope, quote, sections, evidence) live in JSON columns so the
demo needs no migration tool. Anything queried, filtered, sorted, or shown in a
list view gets its own scalar column — status, account name, currency, totals,
timestamps. Money columns are Integer, never Numeric or Float (I9).
"""

from sqlalchemy import JSON, Boolean, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def create_all(engine) -> None:
    Base.metadata.create_all(engine)


class SourceRecordRow(Base):
    __tablename__ = "source_records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    uri: Mapped[str | None] = mapped_column(String, nullable=True)
    retrieved_at: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String)
    excerpt: Mapped[str | None] = mapped_column(String, nullable=True)
    source_type: Mapped[str] = mapped_column(String, index=True)
    approved_for_generation: Mapped[bool] = mapped_column(Boolean, default=False)


class OpportunityRow(Base):
    __tablename__ = "opportunities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    account_name: Mapped[str] = mapped_column(String, index=True)
    contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    source_record_ids: Mapped[list] = mapped_column(JSON, default=list)
    required_field_errors: Mapped[list] = mapped_column(JSON, default=list)
    imported_at: Mapped[str] = mapped_column(String)


class DiscoveryInputRow(Base):
    __tablename__ = "discovery_inputs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)
    source_record_id: Mapped[str] = mapped_column(String)
    extracted_at: Mapped[str] = mapped_column(String)


class RequirementRow(Base):
    __tablename__ = "requirements"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String, index=True)
    text: Mapped[str] = mapped_column(String)
    source_record_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, index=True)
    confidence: Mapped[str] = mapped_column(String)


class ProposalRow(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class ProposalVersionRow(Base):
    __tablename__ = "proposal_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    scope_json: Mapped[dict] = mapped_column(JSON)
    quote_json: Mapped[dict] = mapped_column(JSON)
    claim_ids: Mapped[list] = mapped_column(JSON, default=list)
    source_record_ids: Mapped[list] = mapped_column(JSON, default=list)
    unresolved_flags: Mapped[list] = mapped_column(JSON, default=list)
    total_minor: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String)
    locked_at: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)


class GeneratedSectionRow(Base):
    __tablename__ = "generated_sections"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_version_id: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str] = mapped_column(String, index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    blocks_json: Mapped[list] = mapped_column(JSON, default=list)


class ClaimRow(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    text: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    source_record_ids: Mapped[list] = mapped_column(JSON, default=list)
    valid_from: Mapped[str | None] = mapped_column(String, nullable=True)
    valid_until: Mapped[str | None] = mapped_column(String, nullable=True)
    allowed_contexts: Mapped[list] = mapped_column(JSON, default=list)
    prohibited_contexts: Mapped[list] = mapped_column(JSON, default=list)


class EvidenceLinkRow(Base):
    __tablename__ = "evidence_links"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    claim_id: Mapped[str] = mapped_column(String, index=True)
    source_record_id: Mapped[str] = mapped_column(String)
    locator: Mapped[str] = mapped_column(String)
    excerpt: Mapped[str] = mapped_column(String)
    verified_by: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_at: Mapped[str | None] = mapped_column(String, nullable=True)


class PricingRuleRow(Base):
    __tablename__ = "pricing_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[str] = mapped_column(String)
    label: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String)
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    min_quantity: Mapped[float] = mapped_column(Float)
    max_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    optional: Mapped[bool] = mapped_column(Boolean, default=False)
    active_from: Mapped[str] = mapped_column(String)
    active_until: Mapped[str | None] = mapped_column(String, nullable=True)
    discount_policy_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_record_ids: Mapped[list] = mapped_column(JSON, default=list)


class DiscountPolicyRow(Base):
    __tablename__ = "discount_policies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[str] = mapped_column(String)
    max_percent_without_approval: Mapped[float] = mapped_column(Float)
    max_minor_without_approval: Mapped[int] = mapped_column(Integer)
    requires_quote_approval_above: Mapped[int] = mapped_column(Integer)


class ApprovalRow(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_version_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    required_role: Mapped[str] = mapped_column(String)
    decision: Mapped[str] = mapped_column(String, index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[str | None] = mapped_column(String, nullable=True)


class DocumentRow(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_version_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    content_type: Mapped[str] = mapped_column(String, default="application/pdf")
    storage_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
    ready_at: Mapped[str | None] = mapped_column(String, nullable=True)


class EngagementRecordRow(Base):
    __tablename__ = "engagement_records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_version_id: Mapped[str] = mapped_column(String, index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String, index=True)
    document_id: Mapped[str | None] = mapped_column(String, nullable=True)
    at: Mapped[str] = mapped_column(String, index=True)


class AuditEventRow(Base):
    """Append-only by policy (Task 7). No update path exists on its repository."""

    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    actor_type: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, index=True)
    entity_type: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    before_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    after_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, index=True)

