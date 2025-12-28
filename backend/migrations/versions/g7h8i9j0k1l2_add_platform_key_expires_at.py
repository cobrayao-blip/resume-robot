"""add_platform_key_expires_at

Revision ID: g7h8i9j0k1l2
Revises: f1a2b3c4d5e6
Create Date: 2025-12-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'g7h8i9j0k1l2'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add platform_key_expires_at column to users table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'platform_key_expires_at' not in columns:
        op.add_column('users', sa.Column('platform_key_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'platform_key_expires_at' in columns:
        op.drop_column('users', 'platform_key_expires_at')

