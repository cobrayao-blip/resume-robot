"""add_tenant_support_and_tenant_id_fields

Revision ID: d449f438bceb
Revises: d7062cd86ef2
Create Date: 2025-12-24 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd449f438bceb'
down_revision = 'd7062cd86ef2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========== 创建租户表 ==========
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('subscription_plan', sa.String(length=50), nullable=True, server_default='trial'),
        sa.Column('subscription_start', sa.DateTime(), nullable=True),
        sa.Column('subscription_end', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='active'),
        sa.Column('max_users', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('max_jobs', sa.Integer(), nullable=True, server_default='10'),
        sa.Column('max_resumes_per_month', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('current_month_resume_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenants_id'), 'tenants', ['id'], unique=False)
    op.create_index(op.f('ix_tenants_name'), 'tenants', ['name'], unique=False)
    op.create_index(op.f('ix_tenants_domain'), 'tenants', ['domain'], unique=True)
    op.create_index(op.f('ix_tenants_status'), 'tenants', ['status'], unique=False)
    op.create_index(op.f('ix_tenants_created_at'), 'tenants', ['created_at'], unique=False)
    
    # ========== 创建订阅套餐表 ==========
    op.create_table('subscription_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('monthly_price', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('yearly_price', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('max_users', sa.Integer(), nullable=True),
        sa.Column('max_jobs', sa.Integer(), nullable=True),
        sa.Column('max_resumes_per_month', sa.Integer(), nullable=True),
        sa.Column('enable_batch_operations', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('enable_advanced_matching', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('enable_custom_reports', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('enable_api_access', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_visible', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_subscription_plans_id'), 'subscription_plans', ['id'], unique=False)
    
    # ========== 为所有业务表添加tenant_id字段 ==========
    
    # 1. users表
    op.add_column('users', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_users_tenant_id', 'users', 'tenants', ['tenant_id'], ['id'])
    # 移除email的唯一约束，添加tenant_id+email的唯一约束
    op.drop_index('ix_users_email', table_name='users')
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    op.create_unique_constraint('uq_user_tenant_email', 'users', ['tenant_id', 'email'])
    # 添加role字段
    op.add_column('users', sa.Column('role', sa.String(length=50), nullable=True, server_default='hr_user'))
    
    # 2. job_positions表
    op.add_column('job_positions', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_job_positions_tenant_id'), 'job_positions', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_job_positions_tenant_id', 'job_positions', 'tenants', ['tenant_id'], ['id'])
    
    # 3. filter_rules表
    op.add_column('filter_rules', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_filter_rules_tenant_id'), 'filter_rules', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_filter_rules_tenant_id', 'filter_rules', 'tenants', ['tenant_id'], ['id'])
    
    # 4. resume_job_matches表
    op.add_column('resume_job_matches', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_resume_job_matches_tenant_id'), 'resume_job_matches', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_resume_job_matches_tenant_id', 'resume_job_matches', 'tenants', ['tenant_id'], ['id'])
    
    # 5. company_info表
    op.add_column('company_info', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_company_info_tenant_id'), 'company_info', ['tenant_id'], unique=True)
    op.create_foreign_key('fk_company_info_tenant_id', 'company_info', 'tenants', ['tenant_id'], ['id'])
    
    # 6. match_models表
    op.add_column('match_models', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_match_models_tenant_id'), 'match_models', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_match_models_tenant_id', 'match_models', 'tenants', ['tenant_id'], ['id'])
    
    # 7. candidate_resumes表
    op.add_column('candidate_resumes', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_candidate_resumes_tenant_id'), 'candidate_resumes', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_candidate_resumes_tenant_id', 'candidate_resumes', 'tenants', ['tenant_id'], ['id'])
    
    # 8. resume_templates表
    op.add_column('resume_templates', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_resume_templates_tenant_id'), 'resume_templates', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_resume_templates_tenant_id', 'resume_templates', 'tenants', ['tenant_id'], ['id'])
    
    # 9. source_files表
    op.add_column('source_files', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_source_files_tenant_id'), 'source_files', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_source_files_tenant_id', 'source_files', 'tenants', ['tenant_id'], ['id'])
    
    # 10. parsed_resumes表
    op.add_column('parsed_resumes', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_parsed_resumes_tenant_id'), 'parsed_resumes', ['tenant_id'], unique=False)
    op.create_foreign_key('fk_parsed_resumes_tenant_id', 'parsed_resumes', 'tenants', ['tenant_id'], ['id'])


def downgrade() -> None:
    # ========== 移除tenant_id字段 ==========
    
    # 10. parsed_resumes表
    op.drop_constraint('fk_parsed_resumes_tenant_id', 'parsed_resumes', type_='foreignkey')
    op.drop_index(op.f('ix_parsed_resumes_tenant_id'), table_name='parsed_resumes')
    op.drop_column('parsed_resumes', 'tenant_id')
    
    # 9. source_files表
    op.drop_constraint('fk_source_files_tenant_id', 'source_files', type_='foreignkey')
    op.drop_index(op.f('ix_source_files_tenant_id'), table_name='source_files')
    op.drop_column('source_files', 'tenant_id')
    
    # 8. resume_templates表
    op.drop_constraint('fk_resume_templates_tenant_id', 'resume_templates', type_='foreignkey')
    op.drop_index(op.f('ix_resume_templates_tenant_id'), table_name='resume_templates')
    op.drop_column('resume_templates', 'tenant_id')
    
    # 7. candidate_resumes表
    op.drop_constraint('fk_candidate_resumes_tenant_id', 'candidate_resumes', type_='foreignkey')
    op.drop_index(op.f('ix_candidate_resumes_tenant_id'), table_name='candidate_resumes')
    op.drop_column('candidate_resumes', 'tenant_id')
    
    # 6. match_models表
    op.drop_constraint('fk_match_models_tenant_id', 'match_models', type_='foreignkey')
    op.drop_index(op.f('ix_match_models_tenant_id'), table_name='match_models')
    op.drop_column('match_models', 'tenant_id')
    
    # 5. company_info表
    op.drop_constraint('fk_company_info_tenant_id', 'company_info', type_='foreignkey')
    op.drop_index(op.f('ix_company_info_tenant_id'), table_name='company_info')
    op.drop_column('company_info', 'tenant_id')
    
    # 4. resume_job_matches表
    op.drop_constraint('fk_resume_job_matches_tenant_id', 'resume_job_matches', type_='foreignkey')
    op.drop_index(op.f('ix_resume_job_matches_tenant_id'), table_name='resume_job_matches')
    op.drop_column('resume_job_matches', 'tenant_id')
    
    # 3. filter_rules表
    op.drop_constraint('fk_filter_rules_tenant_id', 'filter_rules', type_='foreignkey')
    op.drop_index(op.f('ix_filter_rules_tenant_id'), table_name='filter_rules')
    op.drop_column('filter_rules', 'tenant_id')
    
    # 2. job_positions表
    op.drop_constraint('fk_job_positions_tenant_id', 'job_positions', type_='foreignkey')
    op.drop_index(op.f('ix_job_positions_tenant_id'), table_name='job_positions')
    op.drop_column('job_positions', 'tenant_id')
    
    # 1. users表
    op.drop_constraint('uq_user_tenant_email', 'users', type_='unique')
    op.drop_index('ix_users_email', table_name='users')
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.drop_constraint('fk_users_tenant_id', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_column('users', 'role')
    op.drop_column('users', 'tenant_id')
    
    # ========== 删除订阅套餐表 ==========
    op.drop_index(op.f('ix_subscription_plans_id'), table_name='subscription_plans')
    op.drop_table('subscription_plans')
    
    # ========== 删除租户表 ==========
    op.drop_index(op.f('ix_tenants_created_at'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_status'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_domain'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_name'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_id'), table_name='tenants')
    op.drop_table('tenants')
