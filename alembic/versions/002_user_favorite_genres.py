"""Add favorite_genres to users

Revision ID: 002
Revises: 001
Create Date: 2026-11-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('favorite_genres', postgresql.ARRAY(sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'favorite_genres')
