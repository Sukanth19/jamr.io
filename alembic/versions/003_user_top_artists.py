"""Add top_artists to users

Revision ID: 003
Revises: 002
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('top_artists', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'top_artists')
