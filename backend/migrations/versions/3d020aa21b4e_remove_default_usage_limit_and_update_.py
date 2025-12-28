"""remove_default_usage_limit_and_update_existing_users

Revision ID: 3d020aa21b4e
Revises: 0d699d2e281f
Create Date: 2025-12-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3d020aa21b4e'
down_revision = '7ac4288deb22'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 移除 monthly_usage_limit 的默认值
    # 首先检查是否有默认值约束
    from sqlalchemy import inspect, text
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # 检查 users 表是否存在
    tables = inspector.get_table_names()
    if 'users' in tables:
        columns = inspector.get_columns('users')
        monthly_usage_limit_col = next((col for col in columns if col['name'] == 'monthly_usage_limit'), None)
        
        if monthly_usage_limit_col:
            # 检查是否有 server_default
            if monthly_usage_limit_col.get('server_default'):
                # 移除默认值约束
                op.alter_column('users', 'monthly_usage_limit',
                              server_default=None,
                              existing_type=sa.Integer(),
                              existing_nullable=True)
            
            # 更新现有用户：将普通用户的默认值3改为NULL（必须由管理员设置）
            # 超级管理员和模板设计师保持NULL（不受限制）
            conn.execute(text("""
                UPDATE users 
                SET monthly_usage_limit = NULL 
                WHERE monthly_usage_limit = 3 
                AND user_type NOT IN ('super_admin', 'template_designer')
            """))


def downgrade() -> None:
    # 恢复默认值（如果需要回滚）
    op.alter_column('users', 'monthly_usage_limit',
                  server_default='3',
                  existing_type=sa.Integer(),
                  existing_nullable=True)
