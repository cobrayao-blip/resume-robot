"""add_system_settings_table

Revision ID: 4a1b2c3d4e5f
Revises: 3d020aa21b4e
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4a1b2c3d4e5f'
down_revision = '3d020aa21b4e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建system_settings表
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False, comment='配置键，如: llm.deepseek.api_key'),
        sa.Column('value', sa.Text(), nullable=True, comment='配置值（加密存储）'),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='system', comment='配置分类: llm, system, email等'),
        sa.Column('description', sa.Text(), nullable=True, comment='配置说明'),
        sa.Column('is_encrypted', sa.Boolean(), nullable=True, server_default='false', comment='是否加密存储'),
        sa.Column('updated_by', sa.Integer(), nullable=True, comment='最后更新人ID'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    
    # 创建索引
    op.create_index('ix_system_settings_key', 'system_settings', ['key'], unique=False)
    op.create_index('idx_category_key', 'system_settings', ['category', 'key'], unique=False)


def downgrade() -> None:
    # 删除索引
    op.drop_index('idx_category_key', table_name='system_settings')
    op.drop_index('ix_system_settings_key', table_name='system_settings')
    
    # 删除表
    op.drop_table('system_settings')

