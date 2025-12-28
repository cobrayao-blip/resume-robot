"""add_job_management_tables

Revision ID: d7062cd86ef2
Revises: h8i9j0k1l2m3
Create Date: 2025-12-24 11:35:18.565956

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7062cd86ef2'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建岗位表
    op.create_table('job_positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('requirements', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='draft'),
        sa.Column('mongodb_id', sa.String(length=255), nullable=True),
        sa.Column('vector_id', sa.String(length=255), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_job_positions_id'), 'job_positions', ['id'], unique=False)
    op.create_index(op.f('ix_job_positions_title'), 'job_positions', ['title'], unique=False)
    op.create_index(op.f('ix_job_positions_status'), 'job_positions', ['status'], unique=False)
    op.create_index(op.f('ix_job_positions_created_by'), 'job_positions', ['created_by'], unique=False)
    op.create_index(op.f('ix_job_positions_created_at'), 'job_positions', ['created_at'], unique=False)
    op.create_index('idx_job_status_created', 'job_positions', ['status', 'created_at'], unique=False)
    op.create_index('idx_job_created_by_status', 'job_positions', ['created_by', 'status'], unique=False)
    
    # 创建筛选规则表
    op.create_table('filter_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(length=50), nullable=False),
        sa.Column('rule_config', sa.JSON(), nullable=False),
        sa.Column('logic_operator', sa.String(length=10), nullable=True, server_default='AND'),
        sa.Column('priority', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_filter_rules_id'), 'filter_rules', ['id'], unique=False)
    op.create_index(op.f('ix_filter_rules_rule_type'), 'filter_rules', ['rule_type'], unique=False)
    op.create_index(op.f('ix_filter_rules_is_active'), 'filter_rules', ['is_active'], unique=False)
    op.create_index(op.f('ix_filter_rules_created_by'), 'filter_rules', ['created_by'], unique=False)
    op.create_index('idx_filter_rule_type_active', 'filter_rules', ['rule_type', 'is_active'], unique=False)
    
    # 创建简历岗位匹配表
    op.create_table('resume_job_matches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('match_score', sa.Float(), nullable=False),
        sa.Column('match_label', sa.String(length=50), nullable=True),
        sa.Column('mongodb_detail_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['job_id'], ['job_positions.id'], ),
        sa.ForeignKeyConstraint(['resume_id'], ['candidate_resumes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resume_job_matches_id'), 'resume_job_matches', ['id'], unique=False)
    op.create_index(op.f('ix_resume_job_matches_resume_id'), 'resume_job_matches', ['resume_id'], unique=False)
    op.create_index(op.f('ix_resume_job_matches_job_id'), 'resume_job_matches', ['job_id'], unique=False)
    op.create_index(op.f('ix_resume_job_matches_match_score'), 'resume_job_matches', ['match_score'], unique=False)
    op.create_index(op.f('ix_resume_job_matches_match_label'), 'resume_job_matches', ['match_label'], unique=False)
    op.create_index(op.f('ix_resume_job_matches_status'), 'resume_job_matches', ['status'], unique=False)
    op.create_index(op.f('ix_resume_job_matches_created_at'), 'resume_job_matches', ['created_at'], unique=False)
    op.create_index('idx_match_resume_job', 'resume_job_matches', ['resume_id', 'job_id'], unique=True)
    op.create_index('idx_match_job_score', 'resume_job_matches', ['job_id', 'match_score'], unique=False)
    op.create_index('idx_match_label_status', 'resume_job_matches', ['match_label', 'status'], unique=False)
    
    # 创建公司信息表
    op.create_table('company_info',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('products', sa.Text(), nullable=True),
        sa.Column('application_scenarios', sa.Text(), nullable=True),
        sa.Column('company_culture', sa.Text(), nullable=True),
        sa.Column('preferences', sa.Text(), nullable=True),
        sa.Column('additional_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_company_info_id'), 'company_info', ['id'], unique=False)
    
    # 创建匹配模型表
    op.create_table('match_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model_type', sa.String(length=50), nullable=False),
        sa.Column('model_config', sa.JSON(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_models_id'), 'match_models', ['id'], unique=False)
    op.create_index(op.f('ix_match_models_model_type'), 'match_models', ['model_type'], unique=False)
    op.create_index(op.f('ix_match_models_is_default'), 'match_models', ['is_default'], unique=False)
    op.create_index(op.f('ix_match_models_is_active'), 'match_models', ['is_active'], unique=False)
    op.create_index('idx_match_model_type_active', 'match_models', ['model_type', 'is_active'], unique=False)


def downgrade() -> None:
    # 删除匹配模型表
    op.drop_index('idx_match_model_type_active', table_name='match_models')
    op.drop_index(op.f('ix_match_models_is_active'), table_name='match_models')
    op.drop_index(op.f('ix_match_models_is_default'), table_name='match_models')
    op.drop_index(op.f('ix_match_models_model_type'), table_name='match_models')
    op.drop_index(op.f('ix_match_models_id'), table_name='match_models')
    op.drop_table('match_models')
    
    # 删除公司信息表
    op.drop_index(op.f('ix_company_info_id'), table_name='company_info')
    op.drop_table('company_info')
    
    # 删除简历岗位匹配表
    op.drop_index('idx_match_label_status', table_name='resume_job_matches')
    op.drop_index('idx_match_job_score', table_name='resume_job_matches')
    op.drop_index('idx_match_resume_job', table_name='resume_job_matches')
    op.drop_index(op.f('ix_resume_job_matches_created_at'), table_name='resume_job_matches')
    op.drop_index(op.f('ix_resume_job_matches_status'), table_name='resume_job_matches')
    op.drop_index(op.f('ix_resume_job_matches_match_label'), table_name='resume_job_matches')
    op.drop_index(op.f('ix_resume_job_matches_match_score'), table_name='resume_job_matches')
    op.drop_index(op.f('ix_resume_job_matches_job_id'), table_name='resume_job_matches')
    op.drop_index(op.f('ix_resume_job_matches_resume_id'), table_name='resume_job_matches')
    op.drop_index(op.f('ix_resume_job_matches_id'), table_name='resume_job_matches')
    op.drop_table('resume_job_matches')
    
    # 删除筛选规则表
    op.drop_index('idx_filter_rule_type_active', table_name='filter_rules')
    op.drop_index(op.f('ix_filter_rules_created_by'), table_name='filter_rules')
    op.drop_index(op.f('ix_filter_rules_is_active'), table_name='filter_rules')
    op.drop_index(op.f('ix_filter_rules_rule_type'), table_name='filter_rules')
    op.drop_index(op.f('ix_filter_rules_id'), table_name='filter_rules')
    op.drop_table('filter_rules')
    
    # 删除岗位表
    op.drop_index('idx_job_created_by_status', table_name='job_positions')
    op.drop_index('idx_job_status_created', table_name='job_positions')
    op.drop_index(op.f('ix_job_positions_created_at'), table_name='job_positions')
    op.drop_index(op.f('ix_job_positions_created_by'), table_name='job_positions')
    op.drop_index(op.f('ix_job_positions_status'), table_name='job_positions')
    op.drop_index(op.f('ix_job_positions_title'), table_name='job_positions')
    op.drop_index(op.f('ix_job_positions_id'), table_name='job_positions')
    op.drop_table('job_positions')


