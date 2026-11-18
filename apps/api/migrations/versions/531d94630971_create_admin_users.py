"""create admin_users

Revision ID: 531d94630971
Revises: 714bacba5259
Create Date: 2026-11-18 13:19:50.398182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '531d94630971'
down_revision: Union[str, Sequence[str], None] = '714bacba5259'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE admin_users (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX admin_users_email_lower_idx ON admin_users (LOWER(email));
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        DROP TABLE admin_users;
        """
    )