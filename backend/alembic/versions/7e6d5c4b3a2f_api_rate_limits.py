"""database backed API rate limits

Revision ID: 7e6d5c4b3a2f
Revises: 6c5d4e3f2a1b
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7e6d5c4b3a2f"
down_revision: Union[str, Sequence[str], None] = "6c5d4e3f2a1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_rate_limit",
        sa.Column("bucket_key", sa.String(length=200), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("bucket_key"),
        schema="pantryops",
    )
    op.create_index(
        "ix_api_rate_limit_expires_at",
        "api_rate_limit",
        ["expires_at"],
        unique=False,
        schema="pantryops",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_api_rate_limit_expires_at",
        table_name="api_rate_limit",
        schema="pantryops",
    )
    op.drop_table("api_rate_limit", schema="pantryops")
