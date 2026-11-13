"""create chunks

Revision ID: 081e168cac09
Revises: b78cb6ba1f0c
Create Date: 2026-11-13 17:42:38.786955

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '081e168cac09'
down_revision: Union[str, Sequence[str], None] = 'b78cb6ba1f0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""CREATE TABLE chunks (
        id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
        position INTEGER NOT NULL,
        text TEXT NOT NULL,
        UNIQUE(source_id, position)
        )""")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE chunks")
