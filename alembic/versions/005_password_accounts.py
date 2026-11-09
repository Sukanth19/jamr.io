"""Add username/password accounts; make Spotify optional

Revision ID: 005
Revises: 004
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(24), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.Text(), nullable=True))
    # Usernames are unique regardless of case
    op.create_index('uq_users_username_lower', 'users', [sa.text('lower(username)')], unique=True)
    # Accounts made with a password have no Spotify account or tokens
    op.alter_column('users', 'spotify_id', existing_type=sa.String(255), nullable=True)
    op.alter_column('users', 'access_token_encrypted', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'access_token_encrypted', existing_type=sa.Text(), nullable=False)
    op.alter_column('users', 'spotify_id', existing_type=sa.String(255), nullable=False)
    op.drop_index('uq_users_username_lower', table_name='users')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'username')
