"""add_user_llm_config

Revision ID: f1a2b3c4d5e6
Revises: de3fceb78d78
Create Date: 2025-12-04 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'de3fceb78d78'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_llm_configs table if not exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if 'user_llm_configs' not in tables:
        op.create_table(
            'user_llm_configs',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('api_key', sa.Text(), nullable=True),
            sa.Column('base_url', sa.String(length=255), nullable=True),
            sa.Column('model_name', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        )
        op.create_index('ix_user_llm_configs_id', 'user_llm_configs', ['id'], unique=False)
        op.create_index('ix_user_llm_configs_user_id', 'user_llm_configs', ['user_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    if 'user_llm_configs' in tables:
        op.drop_index('ix_user_llm_configs_user_id', table_name='user_llm_configs')
        op.drop_index('ix_user_llm_configs_id', table_name='user_llm_configs')
        op.drop_table('user_llm_configs')


