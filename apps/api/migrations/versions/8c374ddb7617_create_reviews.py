"""create reviews

Revision ID: 8c374ddb7617
Revises: 531d94630971
Create Date: 2026-11-18 16:29:31.308273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c374ddb7617'
down_revision: Union[str, Sequence[str], None] = '531d94630971'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Raw string (r"""): keeps the backslash in '\S' for Postgres instead of
    # Python treating it as an escape sequence.
    op.execute(r"""
        CREATE TABLE reviews (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            item_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT,
            decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT reviews_item_id_fkey
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
            CONSTRAINT reviews_reviewer_id_fkey
                FOREIGN KEY (reviewer_id) REFERENCES admin_users (id) ON DELETE RESTRICT,
            CONSTRAINT reviews_decision_check
                CHECK (decision IN ('approved', 'rejected')),
            CONSTRAINT reviews_reason_required_check
                CHECK (decision = 'approved' OR reason IS NOT NULL),
            CONSTRAINT reviews_reason_not_blank_check
                CHECK (reason ~ '\S')
        );
    """)
    # Not UNIQUE: many reviews per item. Serves "latest review for item X"
    # and the RESTRICT check when an item is deleted.
    op.execute("""
        CREATE INDEX reviews_item_id_decided_at_idx
            ON reviews (item_id, decided_at DESC, id DESC);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        DROP TABLE reviews;
    """)
