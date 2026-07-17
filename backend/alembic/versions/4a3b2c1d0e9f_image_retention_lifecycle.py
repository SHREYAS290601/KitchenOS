"""image retention lifecycle

Revision ID: 4a3b2c1d0e9f
Revises: 3f2e1d0c9b8a
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4a3b2c1d0e9f"
down_revision: Union[str, Sequence[str], None] = "3f2e1d0c9b8a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "image_evidence",
        sa.Column("retention_due_at", sa.DateTime(timezone=True), nullable=True),
        schema="pantryops",
    )
    op.add_column(
        "image_evidence",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="pantryops",
    )
    op.create_index(
        op.f("ix_pantryops_image_evidence_retention_due_at"),
        "image_evidence",
        ["retention_due_at"],
        schema="pantryops",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_pantryops_image_evidence_retention_due_at"),
        table_name="image_evidence",
        schema="pantryops",
    )
    op.drop_column("image_evidence", "deleted_at", schema="pantryops")
    op.drop_column("image_evidence", "retention_due_at", schema="pantryops")
