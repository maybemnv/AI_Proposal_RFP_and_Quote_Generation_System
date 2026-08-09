"""Pydantic mirrors of the canonical PRD contracts.

Fields are snake_case in Python and camelCase on the wire (``alias_generator``),
so JSON payloads match the PRD's TypeScript types verbatim while the Python side
stays idiomatic. ``populate_by_name`` lets both spellings validate.

Money is always integer minor units (I9). Quantities are ``float`` because the
canonical contracts type them as ``number`` and real engagements bill fractional
units (2.5 days); the pricing engine converts them to ``Decimal`` at its own
boundary and refuses floats there.
"""

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

# Aliases kept as plain ``str`` so fixture JSON stays readable and diffable.
UUID = str
ISODateTime = str
CurrencyCode = str
MinorUnits = int

Provider = Literal[
    "hubspot",
    "salesforce",
    "pandadoc",
    "docusign",
    "stripe",
    "google_drive",
    "microsoft_365",
    "manual",
]
SourceType = Literal["crm", "discovery", "content", "rfp", "manual"]
OpportunityStatus = Literal["imported", "normalized", "needs_attention"]
DiscoveryKind = Literal["notes", "transcript", "rfp_text"]
RequirementStatus = Literal["confirmed", "assumption", "open_question"]
Confidence = Literal["high", "medium", "low"]
ClaimStatus = Literal["draft", "pending_approval", "approved", "expired", "rejected"]
ProposalStatus = Literal[
    "assembling", "draft", "in_review", "approved", "delivered", "rejected", "archived"
]
ProposalVersionStatus = Literal["working", "submitted", "locked", "rendered", "delivered"]
QuoteStatus = Literal["calculated", "review_required", "approved", "rejected", "superseded"]
ApprovalKind = Literal["claim", "scope", "quote", "proposal"]
ApprovalRole = Literal["content_editor", "quote_approver", "proposal_approver"]
ApprovalDecision = Literal["pending", "approved", "rejected"]
DocumentStatus = Literal["requested", "rendering", "ready", "failed"]
ModelProvider = Literal["claude", "openai"]
BlockKind = Literal["text", "table", "list", "quote"]
FlagSeverity = Literal["blocking", "warning"]
ClaimUsageValidation = Literal["approved", "blocked"]
ActorType = Literal["user", "system", "provider"]
EngagementType = Literal["sent", "viewed", "signed", "declined", "expired"]
AdapterFailureCode = Literal[
    "AUTH", "NOT_FOUND", "RATE_LIMIT", "UNSUPPORTED", "TEMPORARY", "UNKNOWN"
]
AuditAction = Literal[
    "imported",
    "edited",
    "generated",
    "validated",
    "approved",
    "rejected",
    "locked",
    "rendered",
    "delivered",
    "engagement_received",
]
AuditEntityType = Literal[
    "opportunity", "content", "claim", "proposal", "quote", "document"
]
ValidationFlagCode = Literal[
    "MISSING_SOURCE",
    "UNAPPROVED_CLAIM",
    "EXPIRED_CLAIM",
    "UNRESOLVED_REQUIREMENT",
    "PRICE_MISMATCH",
    "MISSING_APPROVAL",
    "SCHEMA_ERROR",
    "RENDER_ERROR",
]
SectionKey = Literal[
    "executive_summary",
    "understanding",
    "scope",
    "milestones",
    "assumptions",
    "options",
    "pricing",
    "payment_schedule",
    "case_studies",
    "next_steps",
    "rfp_answers",
]

PROVIDERS: tuple[str, ...] = get_args(Provider)
VALIDATION_FLAG_CODES: tuple[str, ...] = get_args(ValidationFlagCode)
SECTION_KEYS: tuple[str, ...] = get_args(SectionKey)
AUDIT_ACTIONS: tuple[str, ...] = get_args(AuditAction)


class CamelModel(BaseModel):
    """Base for every contract type: camelCase wire format, no stray fields."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


# --- Sources and opportunities ---------------------------------------------


class SourceRecord(CamelModel):
    id: UUID
    provider: Provider
    external_id: str | None = None
    title: str
    uri: str | None = None
    retrieved_at: ISODateTime
    content_hash: str
    excerpt: str | None = None
    source_type: SourceType
    approved_for_generation: bool


class Opportunity(CamelModel):
    id: UUID
    external_provider: Provider | None = None
    external_id: str | None = None
    account_name: str
    contact_name: str | None = None
    title: str
    currency: CurrencyCode
    status: OpportunityStatus
    source_record_ids: list[UUID] = []
    required_field_errors: list[str] = []
    imported_at: ISODateTime


class DiscoveryInput(CamelModel):
    id: UUID
    opportunity_id: UUID
    kind: DiscoveryKind
    text: str
    source_record_id: UUID
    extracted_at: ISODateTime


# --- Scope ------------------------------------------------------------------


class Requirement(CamelModel):
    id: UUID
    text: str
    source_record_ids: list[UUID] = []
    status: RequirementStatus
    confidence: Confidence


class Deliverable(CamelModel):
    id: UUID
    name: str
    description: str
    quantity: float
    unit: str
    milestone_ids: list[UUID] = []
    source_record_ids: list[UUID] = []
    optional: bool = False


class Milestone(CamelModel):
    id: UUID
    name: str
    sequence: int
    target_description: str
    source_record_ids: list[UUID] = []


class Assumption(CamelModel):
    id: UUID
    text: str
    source_record_ids: list[UUID] = []
    customer_confirmation_required: bool = False


class Scope(CamelModel):
    deliverables: list[Deliverable] = []
    milestones: list[Milestone] = []
    assumptions: list[Assumption] = []
    exclusions: list[str] = []
    open_questions: list[str] = []


# --- Claims and evidence ----------------------------------------------------


class Claim(CamelModel):
    id: UUID
    text: str
    status: ClaimStatus
    source_record_ids: list[UUID] = []
    valid_from: str | None = None
    valid_until: str | None = None
    allowed_contexts: list[str] = []
    prohibited_contexts: list[str] = []


class EvidenceLink(CamelModel):
    claim_id: UUID
    source_record_id: UUID
    locator: str
    excerpt: str
    verified_by: UUID | None = None
    verified_at: ISODateTime | None = None


class ApprovedClaim(Claim):
    """``Claim & { evidence: EvidenceLink[] }`` from the generation contract."""

    evidence: list[EvidenceLink] = []


# --- Pricing and quotes -----------------------------------------------------


class QuoteLine(CamelModel):
    id: UUID
    label: str
    rule_id: UUID
    quantity: float
    unit_price_minor: MinorUnits
    subtotal_minor: MinorUnits
    optional: bool = False
    selected: bool = True
    source_record_ids: list[UUID] = []


class PaymentInstallment(CamelModel):
    sequence: int
    label: str
    amount_minor: MinorUnits
    due_description: str


class Quote(CamelModel):
    """The canonical contract carries no status field; do not add one here."""

    currency: CurrencyCode
    lines: list[QuoteLine] = []
    subtotal_minor: MinorUnits
    discount_minor: MinorUnits
    tax_minor: MinorUnits
    total_minor: MinorUnits
    payment_schedule: list[PaymentInstallment] = []
    pricing_rule_version: str
    input_hash: str
    calculated_at: ISODateTime


class QuoteCalculationResponse(Quote):
    """A calculated quote plus the approval status the endpoint decided."""

    status: QuoteStatus
    policy_message: str | None = None


class PricingRule(CamelModel):
    id: UUID
    version: str
    label: str
    unit: str
    currency: CurrencyCode
    unit_price_minor: MinorUnits
    min_quantity: float
    max_quantity: float | None = None
    optional: bool = False
    active_from: str
    active_until: str | None = None
    discount_policy_id: UUID | None = None
    source_record_ids: list[UUID] = []


class DiscountPolicy(CamelModel):
    id: UUID
    version: str
    max_percent_without_approval: float
    max_minor_without_approval: MinorUnits
    requires_quote_approval_above: MinorUnits


# --- Proposals, approvals, documents ----------------------------------------


class Proposal(CamelModel):
    id: UUID
    opportunity_id: UUID
    status: ProposalStatus
    title: str
    currency: CurrencyCode
    created_at: ISODateTime


class Approval(CamelModel):
    id: UUID
    proposal_version_id: UUID
    kind: ApprovalKind
    required_role: ApprovalRole
    decision: ApprovalDecision
    reviewer_id: UUID | None = None
    comment: str | None = None
    decided_at: ISODateTime | None = None


class ProposalVersion(CamelModel):
    id: UUID
    proposal_id: UUID
    version_number: int
    status: ProposalVersionStatus
    title: str
    scope: Scope
    quote: Quote
    claim_ids: list[UUID] = []
    source_record_ids: list[UUID] = []
    unresolved_flags: list[str] = []
    created_at: ISODateTime
    locked_at: ISODateTime | None = None


class Document(CamelModel):
    id: UUID
    proposal_version_id: UUID
    status: DocumentStatus
    content_type: str = "application/pdf"
    storage_uri: str | None = None
    content_hash: str | None = None
    created_at: ISODateTime
    ready_at: ISODateTime | None = None


# --- Generation -------------------------------------------------------------


class GenerateDraftRequest(CamelModel):
    proposal_version_id: UUID
    opportunity: Opportunity | None = None
    discovery: list[DiscoveryInput] = []
    requirements: list[Requirement] = []
    scope: Scope | None = None
    approved_claims: list[ApprovedClaim] = []
    template_id: UUID
    requested_sections: list[SectionKey]
    model_provider: ModelProvider
    model_name: str


class GeneratedBlock(CamelModel):
    block_id: UUID
    kind: BlockKind = "text"
    content: str
    claim_ids: list[UUID] = []
    source_record_ids: list[UUID] = []
    editable: bool = True


class GeneratedSection(CamelModel):
    key: str
    blocks: list[GeneratedBlock] = []


class ClaimUsage(CamelModel):
    claim_id: UUID
    block_id: UUID
    evidence_link_ids: list[UUID] = []
    validation: ClaimUsageValidation


class ValidationFlag(CamelModel):
    code: ValidationFlagCode
    severity: FlagSeverity
    message: str
    related_ids: list[UUID] = []


class GenerateDraftResponse(CamelModel):
    proposal_version_id: UUID
    sections: list[GeneratedSection] = []
    claims_used: list[ClaimUsage] = []
    unresolved_flags: list[ValidationFlag] = []
    generation_run_id: UUID
    source_snapshot_hash: str


# --- Audit, adapters, engagement --------------------------------------------


class AuditEvent(CamelModel):
    id: UUID
    workspace_id: UUID
    actor_type: ActorType
    actor_id: UUID | None = None
    action: AuditAction
    entity_type: AuditEntityType
    entity_id: UUID
    before_hash: str | None = None
    after_hash: str | None = None
    metadata: dict[str, str] = {}
    created_at: ISODateTime


class AdapterFailure(CamelModel):
    code: AdapterFailureCode
    provider: Provider
    message: str
    retryable: bool
    external_request_id: str | None = None


class EngagementRecord(CamelModel):
    id: UUID
    proposal_version_id: UUID
    provider: Provider
    type: EngagementType
    document_id: UUID | None = None
    at: ISODateTime
