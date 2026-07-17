"""durable background job

Revision ID: 3f2e1d0c9b8a
Revises: 8a1f3d24c9b7
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "3f2e1d0c9b8a"
down_revision: Union[str, Sequence[str], None] = "8a1f3d24c9b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_job",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("image_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "dispatch_attempts >= 0",
            name="ck_background_job_dispatch_attempts_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'needs_review')",
            name="ck_background_job_status",
        ),
        sa.PrimaryKeyConstraint("job_id"),
        schema="pantryops",
    )
    op.create_index(
        "ix_background_job_dispatch",
        "background_job",
        ["status", "dispatched_at", "created_at"],
        schema="pantryops",
    )
    op.create_index(
        op.f("ix_pantryops_background_job_status"),
        "background_job",
        ["status"],
        schema="pantryops",
    )
    op.create_index(
        op.f("ix_pantryops_background_job_user_id"),
        "background_job",
        ["user_id"],
        schema="pantryops",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_pantryops_background_job_user_id"),
        table_name="background_job",
        schema="pantryops",
    )
    op.drop_index(
        op.f("ix_pantryops_background_job_status"),
        table_name="background_job",
        schema="pantryops",
    )
    op.drop_index(
        "ix_background_job_dispatch",
        table_name="background_job",
        schema="pantryops",
    )
    op.drop_table("background_job", schema="pantryops")
