"""Repositories converting between rows and Pydantic models.

Most aggregates map field-for-field onto their row, so ``Repo`` does the work
once and the concrete classes only declare the pair. The ones that differ —
proposal versions (JSON aggregates + denormalized total), evidence links (no id
in the contract), requirements and sections (owned by a parent) — override.

``VersionRepo.update`` checks the **stored** row's status, never the incoming
model's. That is what makes I5 hold at the storage boundary: a caller cannot
launder a locked version mutable by sending status='working'.
"""

from typing import Any, ClassVar

from sqlalchemy import select

from app.domain.schemas import (
    Approval,
    AuditEvent,
    CamelModel,
    Claim,
    DiscountPolicy,
    DiscoveryInput,
    Document,
    EngagementRecord,
    EvidenceLink,
    GeneratedBlock,
    GeneratedSection,
    Opportunity,
    PricingRule,
    Proposal,
    ProposalVersion,
    Quote,
    Requirement,
    Scope,
    SourceRecord,
)
from app.domain.workflow import assert_mutable, assert_transition, content_hash
from app.persistence.models import (
    ApprovalRow,
    AuditEventRow,
    Base,
    ClaimRow,
    DiscountPolicyRow,
    DiscoveryInputRow,
    DocumentRow,
    EngagementRecordRow,
    EvidenceLinkRow,
    GeneratedSectionRow,
    OpportunityRow,
    PricingRuleRow,
    ProposalRow,
    ProposalVersionRow,
    RequirementRow,
    SourceRecordRow,
)


class Repo:
    """Field-for-field mapping between one model type and one row type."""

    model: ClassVar[type[CamelModel]]
    row: ClassVar[type[Base]]

    def __init__(self, session):
        self.s = session

    def _row_values(self, obj: CamelModel) -> dict[str, Any]:
        return obj.model_dump()

    def _to_model(self, row: Base) -> CamelModel:
        return self.model.model_validate(
            {name: getattr(row, name) for name in self.model.model_fields}
        )

    def add(self, obj: CamelModel) -> None:
        self.s.add(self.row(**self._row_values(obj)))

    def get(self, key: str) -> Any:
        row = self.s.get(self.row, key)
        if row is None:
            raise KeyError(key)
        return self._to_model(row)

    def find(self, key: str) -> Any | None:
        row = self.s.get(self.row, key)
        return None if row is None else self._to_model(row)

    def list(self, **filters: Any) -> list[Any]:
        stmt = select(self.row)
        for column, value in filters.items():
            stmt = stmt.where(getattr(self.row, column) == value)
        return [self._to_model(row) for row in self.s.scalars(stmt)]

    def update(self, obj: CamelModel) -> None:
        row = self.s.get(self.row, obj.id)
        if row is None:
            raise KeyError(obj.id)
        for column, value in self._row_values(obj).items():
            setattr(row, column, value)


class SourceRecordRepo(Repo):
    model, row = SourceRecord, SourceRecordRow


class OpportunityRepo(Repo):
    model, row = Opportunity, OpportunityRow


class DiscoveryRepo(Repo):
    model, row = DiscoveryInput, DiscoveryInputRow


class ProposalRepo(Repo):
    model, row = Proposal, ProposalRow


class ClaimRepo(Repo):
    model, row = Claim, ClaimRow


class PricingRuleRepo(Repo):
    model, row = PricingRule, PricingRuleRow


class DiscountPolicyRepo(Repo):
    model, row = DiscountPolicy, DiscountPolicyRow


class ApprovalRepo(Repo):
    model, row = Approval, ApprovalRow


class DocumentRepo(Repo):
    model, row = Document, DocumentRow


class EngagementRepo(Repo):
    model, row = EngagementRecord, EngagementRecordRow

    def list_for_version(self, proposal_version_id: str) -> list[EngagementRecord]:
        stmt = (
            select(EngagementRecordRow)
            .where(EngagementRecordRow.proposal_version_id == proposal_version_id)
            .order_by(EngagementRecordRow.at)
        )
        return [self._to_model(row) for row in self.s.scalars(stmt)]


class AuditRepo(Repo):
    """Read and append only. ``update`` and ``delete`` exist solely to refuse."""

    model, row = AuditEvent, AuditEventRow

    def _to_model(self, row: AuditEventRow) -> AuditEvent:
        return AuditEvent(
            id=row.id,
            workspace_id=row.workspace_id,
            actor_type=row.actor_type,
            actor_id=row.actor_id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            before_hash=row.before_hash,
            after_hash=row.after_hash,
            metadata=row.event_metadata,
            created_at=row.created_at,
        )

    def _ordered(self, *conditions) -> list[AuditEvent]:
        stmt = select(AuditEventRow).order_by(AuditEventRow.created_at, AuditEventRow.id)
        for condition in conditions:
            stmt = stmt.where(condition)
        return [self._to_model(row) for row in self.s.scalars(stmt)]

    def list_for(self, entity_id: str) -> list[AuditEvent]:
        return self._ordered(AuditEventRow.entity_id == entity_id)

    def list_for_workspace(self, workspace_id: str) -> list[AuditEvent]:
        return self._ordered(AuditEventRow.workspace_id == workspace_id)

    def add(self, obj: AuditEvent) -> None:
        raise NotImplementedError(
            "audit log is append-only: use app.domain.audit.record_event")

    def update(self, obj: AuditEvent) -> None:
        raise NotImplementedError("audit log is append-only: events cannot be updated")

    def delete(self, entity_id: str) -> None:
        raise NotImplementedError("audit log is append-only: events cannot be deleted")


class RequirementRepo(Repo):
    """Requirements belong to an opportunity, which the contract type omits."""

    model, row = Requirement, RequirementRow

    def add_for_opportunity(self, opportunity_id: str, requirement: Requirement) -> None:
        self.s.add(RequirementRow(
            opportunity_id=opportunity_id, **requirement.model_dump()))

    def list_for_opportunity(self, opportunity_id: str) -> list[Requirement]:
        return self.list(opportunity_id=opportunity_id)


class EvidenceRepo(Repo):
    """EvidenceLink has no id in the contract; the row needs one."""

    model, row = EvidenceLink, EvidenceLinkRow

    def add_link(self, link_id: str, link: EvidenceLink) -> None:
        self.s.add(EvidenceLinkRow(id=link_id, **link.model_dump()))

    def list_for_claim(self, claim_id: str) -> list[EvidenceLink]:
        return self.list(claim_id=claim_id)

    def by_claim(self, claim_ids: list[str]) -> dict[str, list[EvidenceLink]]:
        """Shape Task 4's validate_block expects."""
        stmt = select(EvidenceLinkRow).where(EvidenceLinkRow.claim_id.in_(claim_ids))
        grouped: dict[str, list[EvidenceLink]] = {}
        for row in self.s.scalars(stmt):
            grouped.setdefault(row.claim_id, []).append(self._to_model(row))
        return grouped


class SectionRepo(Repo):
    model, row = GeneratedSection, GeneratedSectionRow

    def _to_model(self, row: GeneratedSectionRow) -> GeneratedSection:
        return GeneratedSection(
            key=row.key,
            blocks=[GeneratedBlock.model_validate(b) for b in row.blocks_json],
        )

    def replace_for_version(
        self, proposal_version_id: str, sections: list[GeneratedSection]
    ) -> None:
        for existing in self.s.scalars(
            select(GeneratedSectionRow).where(
                GeneratedSectionRow.proposal_version_id == proposal_version_id)
        ):
            self.s.delete(existing)
        for sequence, section in enumerate(sections):
            self.s.add(GeneratedSectionRow(
                id=f"{proposal_version_id}:{section.key}",
                proposal_version_id=proposal_version_id,
                key=section.key,
                sequence=sequence,
                blocks_json=[b.model_dump(by_alias=True) for b in section.blocks],
            ))

    def list_for_version(self, proposal_version_id: str) -> list[GeneratedSection]:
        stmt = (
            select(GeneratedSectionRow)
            .where(GeneratedSectionRow.proposal_version_id == proposal_version_id)
            .order_by(GeneratedSectionRow.sequence)
        )
        return [self._to_model(row) for row in self.s.scalars(stmt)]


class VersionRepo(Repo):
    model, row = ProposalVersion, ProposalVersionRow

    def _row_values(self, obj: ProposalVersion) -> dict[str, Any]:
        return {
            "id": obj.id,
            "proposal_id": obj.proposal_id,
            "version_number": obj.version_number,
            "status": obj.status,
            "title": obj.title,
            "scope_json": obj.scope.model_dump(by_alias=True),
            "quote_json": obj.quote.model_dump(by_alias=True),
            "claim_ids": list(obj.claim_ids),
            "source_record_ids": list(obj.source_record_ids),
            "unresolved_flags": list(obj.unresolved_flags),
            "total_minor": obj.quote.total_minor,
            "created_at": obj.created_at,
            "locked_at": obj.locked_at,
        }

    def _to_model(self, row: ProposalVersionRow) -> ProposalVersion:
        return ProposalVersion(
            id=row.id,
            proposal_id=row.proposal_id,
            version_number=row.version_number,
            status=row.status,
            title=row.title,
            scope=Scope.model_validate(row.scope_json),
            quote=Quote.model_validate(row.quote_json),
            claim_ids=list(row.claim_ids),
            source_record_ids=list(row.source_record_ids),
            unresolved_flags=list(row.unresolved_flags),
            created_at=row.created_at,
            locked_at=row.locked_at,
        )

    def update(self, version: ProposalVersion) -> None:
        """I5 at the storage boundary — the stored status decides, not the payload."""
        row = self.s.get(ProposalVersionRow, version.id)
        if row is None:
            raise KeyError(version.id)
        assert_mutable(self._to_model(row))
        for column, value in self._row_values(version).items():
            setattr(row, column, value)

    def promote(self, version: ProposalVersion, target: str) -> None:
        """The one path allowed to move a locked version forward (status only)."""
        row = self.s.get(ProposalVersionRow, version.id)
        if row is None:
            raise KeyError(version.id)
        assert_transition("proposal_version", row.status, target)
        row.status = target
        if target == "locked":
            row.locked_at = version.locked_at
            row.content_hash = content_hash(version)

    def next_version_number(self, proposal_id: str) -> int:
        existing = [v.version_number for v in self.list(proposal_id=proposal_id)]
        return max(existing, default=0) + 1

