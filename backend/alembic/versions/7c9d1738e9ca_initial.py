"""initial

Revision ID: 7c9d1738e9ca
Revises: 
Create Date: 2026-07-13 11:04:04.001551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c9d1738e9ca'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Initial revision: no domain tables yet (they arrive in Phase 2)."""
    pass


def downgrade() -> None:
    pass
