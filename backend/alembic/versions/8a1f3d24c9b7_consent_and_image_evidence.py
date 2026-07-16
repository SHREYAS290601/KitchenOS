"""consent and image evidence

Revision ID: 8a1f3d24c9b7
Revises: 05d94948c8d5
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8a1f3d24c9b7"
down_revision: Union[str, Sequence[str], None] = "05d94948c8d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_record",
        sa.Column("consent_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("retention_policy", sa.String(), nullable=False),
        sa.Column("single_image_consumed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("consent_id"),
        sa.UniqueConstraint("user_id", name="uq_consent_record_user"),
        schema="pantryops",
    )
    op.create_index("ix_pantryops_consent_record_user_id", "consent_record", ["user_id"], schema="pantryops")
    op.create_table(
        "image_evidence",
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("capture_context", sa.String(), nullable=False),
        sa.Column("processing_mode", sa.String(), nullable=False),
        sa.Column("linked_shopping_session_id", sa.String(), nullable=True),
        sa.Column("related_item_candidate", sa.String(), nullable=True),
        sa.Column("storage_uri", sa.String(), nullable=False),
        sa.Column("consent_status", sa.String(), nullable=False),
        sa.Column("retention_policy", sa.String(), nullable=False),
        sa.Column("stored_for_future_enrichment", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("image_id"),
        schema="pantryops",
    )
    op.create_index("ix_pantryops_image_evidence_user_id", "image_evidence", ["user_id"], schema="pantryops")
    op.create_index("ix_pantryops_image_evidence_linked_shopping_session_id", "image_evidence", ["linked_shopping_session_id"], schema="pantryops")


def downgrade() -> None:
    op.drop_index("ix_pantryops_image_evidence_linked_shopping_session_id", table_name="image_evidence", schema="pantryops")
    op.drop_index("ix_pantryops_image_evidence_user_id", table_name="image_evidence", schema="pantryops")
    op.drop_table("image_evidence", schema="pantryops")
    op.drop_index("ix_pantryops_consent_record_user_id", table_name="consent_record", schema="pantryops")
    op.drop_table("consent_record", schema="pantryops")
