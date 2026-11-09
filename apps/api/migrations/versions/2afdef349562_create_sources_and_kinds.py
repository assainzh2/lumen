"""create sources and kinds

Revision ID: 2afdef349562
Revises: 
Create Date: 2026-11-09 16:12:47.147499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2afdef349562'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""CREATE TABLE kinds (
        id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""")
    op.execute("""CREATE TABLE sources (
        id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        url TEXT NOT NULL UNIQUE,
        text TEXT NOT NULL,
        fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        licence TEXT NOT NULL
    )""")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE sources")
    op.execute("DROP TABLE kinds")
