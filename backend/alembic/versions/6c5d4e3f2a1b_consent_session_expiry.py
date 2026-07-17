"""consent session expiry

Revision ID: 6c5d4e3f2a1b
Revises: 5b4c3d2e1f0a
Create Date: 2026-07-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "6c5d4e3f2a1b"
down_revision: Union[str, Sequence[str], None] = "5b4c3d2e1f0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consent_record",
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="pantryops",
    )


def downgrade() -> None:
    op.drop_column("consent_record", "session_expires_at", schema="pantryops")
