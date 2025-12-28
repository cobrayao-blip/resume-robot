"""remove_platform_key_expires_at

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2025-12-09 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'h8i9j0k1l2m3'
down_revision = '11fbf97ead8f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove platform_key_expires_at column from users table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'platform_key_expires_at' in columns:
        op.drop_column('users', 'platform_key_expires_at')
        print("已移除 platform_key_expires_at 字段")


def downgrade() -> None:
    """Re-add platform_key_expires_at column to users table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'platform_key_expires_at' not in columns:
        op.add_column('users', sa.Column('platform_key_expires_at', sa.DateTime(), nullable=True))
        print("已恢复 platform_key_expires_at 字段")

