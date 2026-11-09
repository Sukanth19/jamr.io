"""Add user roles and suspensions

Revision ID: 004
Revises: 003
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role', sa.String(16), nullable=False, server_default='user'))
    op.add_column('users', sa.Column('suspended_until', sa.TIMESTAMP(), nullable=True))
    op.create_check_constraint('ck_users_role', 'users', "role IN ('user', 'mod', 'admin', 'overseer')")
    # At most one overseer
    op.create_index('one_overseer', 'users', ['role'], unique=True,
                    postgresql_where=sa.text("role = 'overseer'"))


def downgrade() -> None:
    op.drop_index('one_overseer', table_name='users')
    op.drop_constraint('ck_users_role', 'users', type_='check')
    op.drop_column('users', 'suspended_until')
    op.drop_column('users', 'role')
