"""add_membership_management_fields

Revision ID: 0d699d2e281f
Revises: de3fceb78d78
Create Date: 2025-12-06 11:00:32.728044

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d699d2e281f'
down_revision = 'de3fceb78d78'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 检查 users 表的列
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    tables = inspector.get_table_names()
    
    if 'users' in tables:
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        # 添加注册审核相关字段
        if 'registration_status' not in columns:
            op.add_column('users', sa.Column('registration_status', sa.String(length=50), nullable=True, server_default='pending'))
        if 'reviewed_by' not in columns:
            op.add_column('users', sa.Column('reviewed_by', sa.Integer(), nullable=True))
        if 'reviewed_at' not in columns:
            op.add_column('users', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
        if 'review_notes' not in columns:
            op.add_column('users', sa.Column('review_notes', sa.Text(), nullable=True))
        
        # 添加使用限制相关字段（不设置默认值，必须由管理员设置）
        if 'monthly_usage_limit' not in columns:
            op.add_column('users', sa.Column('monthly_usage_limit', sa.Integer(), nullable=True))
        if 'current_month_usage' not in columns:
            op.add_column('users', sa.Column('current_month_usage', sa.Integer(), nullable=True, server_default='0'))
        if 'usage_reset_date' not in columns:
            op.add_column('users', sa.Column('usage_reset_date', sa.DateTime(), nullable=True))
        
        # 添加外键约束
        if 'reviewed_by' in [col['name'] for col in inspector.get_columns('users')]:
            try:
                op.create_foreign_key(
                    'fk_users_reviewed_by_users',
                    'users', 'users',
                    ['reviewed_by'], ['id'],
                    ondelete='SET NULL'
                )
            except Exception:
                pass  # 外键可能已存在
    
    # 创建用户注册申请表
    if 'user_registration_requests' not in tables:
        op.create_table(
            'user_registration_requests',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('full_name', sa.String(length=100), nullable=False),
            sa.Column('company', sa.String(length=255), nullable=True),
            sa.Column('phone', sa.String(length=50), nullable=True),
            sa.Column('application_reason', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=True, server_default='pending'),
            sa.Column('reviewed_by', sa.Integer(), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('review_notes', sa.Text(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_user_registration_requests_email'), 'user_registration_requests', ['email'], unique=True)
        op.create_index(op.f('ix_user_registration_requests_status'), 'user_registration_requests', ['status'], unique=False)
        op.create_foreign_key(
            'fk_user_registration_requests_reviewed_by_users',
            'user_registration_requests', 'users',
            ['reviewed_by'], ['id'],
            ondelete='SET NULL'
        )
        op.create_foreign_key(
            'fk_user_registration_requests_user_id_users',
            'user_registration_requests', 'users',
            ['user_id'], ['id'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    # 删除用户注册申请表
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    tables = inspector.get_table_names()
    
    if 'user_registration_requests' in tables:
        op.drop_table('user_registration_requests')
    
    # 删除 users 表的新字段
    if 'users' in tables:
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'usage_reset_date' in columns:
            op.drop_column('users', 'usage_reset_date')
        if 'current_month_usage' in columns:
            op.drop_column('users', 'current_month_usage')
        if 'monthly_usage_limit' in columns:
            op.drop_column('users', 'monthly_usage_limit')
        if 'review_notes' in columns:
            op.drop_column('users', 'review_notes')
        if 'reviewed_at' in columns:
            op.drop_column('users', 'reviewed_at')
        if 'reviewed_by' in columns:
            # 先删除外键约束
            try:
                op.drop_constraint('fk_users_reviewed_by_users', 'users', type_='foreignkey')
            except Exception:
                pass
            op.drop_column('users', 'reviewed_by')
        if 'registration_status' in columns:
            op.drop_column('users', 'registration_status')


