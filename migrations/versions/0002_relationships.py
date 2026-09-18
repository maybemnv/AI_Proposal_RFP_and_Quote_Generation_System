"""Add relational and concurrency constraints absent from the prototype models."""
from alembic import op

revision = "0002_relationships"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_unique_constraint("uq_proposal_versions_number", "proposal_versions", ["proposal_id", "version_number"])
    op.create_foreign_key("fk_discovery_opportunity", "discovery_inputs", "opportunities", ["opportunity_id"], ["id"])
    op.create_foreign_key("fk_requirement_opportunity", "requirements", "opportunities", ["opportunity_id"], ["id"])
    op.create_foreign_key("fk_proposal_opportunity", "proposals", "opportunities", ["opportunity_id"], ["id"])
    op.create_foreign_key("fk_version_proposal", "proposal_versions", "proposals", ["proposal_id"], ["id"])
    op.create_foreign_key("fk_section_version", "generated_sections", "proposal_versions", ["proposal_version_id"], ["id"])
    op.create_foreign_key("fk_evidence_claim", "evidence_links", "claims", ["claim_id"], ["id"])
    op.create_foreign_key("fk_evidence_source", "evidence_links", "source_records", ["source_record_id"], ["id"])
    op.create_foreign_key("fk_approval_version", "approvals", "proposal_versions", ["proposal_version_id"], ["id"])
    op.create_foreign_key("fk_document_version", "documents", "proposal_versions", ["proposal_version_id"], ["id"])
    op.create_index("ix_documents_version_status", "documents", ["proposal_version_id", "status"])

def downgrade() -> None:
    op.drop_index("ix_documents_version_status", table_name="documents")
    for name, table in (
        ("fk_document_version", "documents"), ("fk_approval_version", "approvals"),
        ("fk_evidence_source", "evidence_links"), ("fk_evidence_claim", "evidence_links"),
        ("fk_section_version", "generated_sections"), ("fk_version_proposal", "proposal_versions"),
        ("fk_proposal_opportunity", "proposals"), ("fk_requirement_opportunity", "requirements"),
        ("fk_discovery_opportunity", "discovery_inputs"),
    ):
        op.drop_constraint(name, table_name=table, type_="foreignkey")
    op.drop_constraint("uq_proposal_versions_number", table_name="proposal_versions", type_="unique")
