"""job dispatch claims and retention completion

Revision ID: 5b4c3d2e1f0a
Revises: 4a3b2c1d0e9f
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5b4c3d2e1f0a"
down_revision: Union[str, Sequence[str], None] = "4a3b2c1d0e9f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "background_job",
        sa.Column("dispatch_claimed_at", sa.DateTime(timezone=True), nullable=True),
        schema="pantryops",
    )
    op.add_column(
        "background_job",
        sa.Column("retention_enforced_at", sa.DateTime(timezone=True), nullable=True),
        schema="pantryops",
    )


def downgrade() -> None:
    op.drop_column("background_job", "retention_enforced_at", schema="pantryops")
    op.drop_column("background_job", "dispatch_claimed_at", schema="pantryops")
