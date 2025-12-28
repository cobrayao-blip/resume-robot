"""add_department_table_and_enhance_company_job_models

Revision ID: 83c64ef30722
Revises: 96dc123de18d
Create Date: 2025-12-26 10:51:23.468195

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '83c64ef30722'
down_revision = '96dc123de18d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建departments表
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('path', sa.String(length=500), nullable=True),
        sa.Column('department_culture', sa.Text(), nullable=True),
        sa.Column('work_style', sa.Text(), nullable=True),
        sa.Column('team_size', sa.Integer(), nullable=True),
        sa.Column('key_responsibilities', sa.Text(), nullable=True),
        sa.Column('manager_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['parent_id'], ['departments.id'], ),
        sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_departments_id'), 'departments', ['id'], unique=False)
    op.create_index(op.f('ix_departments_tenant_id'), 'departments', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_departments_name'), 'departments', ['name'], unique=False)
    op.create_index(op.f('ix_departments_parent_id'), 'departments', ['parent_id'], unique=False)
    op.create_index(op.f('ix_departments_level'), 'departments', ['level'], unique=False)
    op.create_index(op.f('ix_departments_manager_id'), 'departments', ['manager_id'], unique=False)
    op.create_index('idx_department_tenant_parent', 'departments', ['tenant_id', 'parent_id'], unique=False)
    op.create_index('idx_department_tenant_level', 'departments', ['tenant_id', 'level'], unique=False)
    
    # 2. 增强company_info表（添加新字段）
    op.add_column('company_info', sa.Column('company_size', sa.String(length=50), nullable=True))
    op.add_column('company_info', sa.Column('development_stage', sa.String(length=50), nullable=True))
    op.add_column('company_info', sa.Column('business_model', sa.Text(), nullable=True))
    op.add_column('company_info', sa.Column('core_values', sa.Text(), nullable=True))
    op.add_column('company_info', sa.Column('recruitment_philosophy', sa.Text(), nullable=True))
    
    # 3. 增强job_positions表（添加department_id外键）
    op.add_column('job_positions', sa.Column('department_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_job_positions_department_id', 'job_positions', 'departments', ['department_id'], ['id'])
    op.create_index(op.f('ix_job_positions_department_id'), 'job_positions', ['department_id'], unique=False)


def downgrade() -> None:
    # 3. 回滚job_positions表
    op.drop_index(op.f('ix_job_positions_department_id'), table_name='job_positions')
    op.drop_constraint('fk_job_positions_department_id', 'job_positions', type_='foreignkey')
    op.drop_column('job_positions', 'department_id')
    
    # 2. 回滚company_info表
    op.drop_column('company_info', 'recruitment_philosophy')
    op.drop_column('company_info', 'core_values')
    op.drop_column('company_info', 'business_model')
    op.drop_column('company_info', 'development_stage')
    op.drop_column('company_info', 'company_size')
    
    # 1. 删除departments表
    op.drop_index('idx_department_tenant_level', table_name='departments')
    op.drop_index('idx_department_tenant_parent', table_name='departments')
    op.drop_index(op.f('ix_departments_manager_id'), table_name='departments')
    op.drop_index(op.f('ix_departments_level'), table_name='departments')
    op.drop_index(op.f('ix_departments_parent_id'), table_name='departments')
    op.drop_index(op.f('ix_departments_name'), table_name='departments')
    op.drop_index(op.f('ix_departments_tenant_id'), table_name='departments')
    op.drop_index(op.f('ix_departments_id'), table_name='departments')
    op.drop_table('departments')
