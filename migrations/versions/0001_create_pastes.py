"""Create the pastes table.

Revision ID: 0001
Revises:
Create Date: 2026-11-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pastes",
        sa.Column("id", sa.String(8), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pastes_expires_at", "pastes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_pastes_expires_at", table_name="pastes")
    op.drop_table("pastes")
