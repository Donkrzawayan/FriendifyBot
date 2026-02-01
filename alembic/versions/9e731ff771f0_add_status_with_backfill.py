"""add_status_with_backfill

Revision ID: 9e731ff771f0
Revises:
Create Date: 2026-02-01 16:21:05.606720

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9e731ff771f0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENUM_NAME = "RoundStatus"
ENUM_VALUES = ["IN_PROGRESS", "COMPLETED", "CANCELLED", "ERROR"]


def upgrade() -> None:
    """Upgrade schema."""
    round_status_enum = postgresql.ENUM(*ENUM_VALUES, name=ENUM_NAME)
    round_status_enum.create(op.get_bind())

    op.add_column("rounds", sa.Column("status", sa.Enum(*ENUM_VALUES, name=ENUM_NAME), nullable=True))
    op.execute("UPDATE rounds SET status = 'COMPLETED'")
    op.alter_column("rounds", "status", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("rounds", "status")
    postgresql.Enum(*ENUM_VALUES, name=ENUM_NAME).drop(op.get_bind())
