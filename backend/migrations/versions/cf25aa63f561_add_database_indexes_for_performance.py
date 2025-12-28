"""add_database_indexes_for_performance

Revision ID: cf25aa63f561
Revises: 485ef4294586
Create Date: 2025-11-25 10:51:08.339406

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf25aa63f561'
down_revision = '485ef4294586'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 检查索引是否已存在，如果不存在则创建（避免重复创建错误）
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # 为 ResumeTemplate 表添加索引
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('resume_templates')]
    if 'ix_resume_templates_is_public' not in existing_indexes:
        op.create_index('ix_resume_templates_is_public', 'resume_templates', ['is_public'], unique=False)
    if 'ix_resume_templates_is_active' not in existing_indexes:
        op.create_index('ix_resume_templates_is_active', 'resume_templates', ['is_active'], unique=False)
    if 'ix_resume_templates_created_by' not in existing_indexes:
        op.create_index('ix_resume_templates_created_by', 'resume_templates', ['created_by'], unique=False)
    if 'idx_template_public_active' not in existing_indexes:
        op.create_index('idx_template_public_active', 'resume_templates', ['is_public', 'is_active'], unique=False)
    if 'idx_template_created_by_active' not in existing_indexes:
        op.create_index('idx_template_created_by_active', 'resume_templates', ['created_by', 'is_active'], unique=False)
    
    # 为 TemplateVersion 表添加索引
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('template_versions')]
    if 'ix_template_versions_template_id' not in existing_indexes:
        op.create_index('ix_template_versions_template_id', 'template_versions', ['template_id'], unique=False)
    if 'ix_template_versions_created_at' not in existing_indexes:
        op.create_index('ix_template_versions_created_at', 'template_versions', ['created_at'], unique=False)
    
    # 为 UserResume 表添加索引
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('user_resumes')]
    if 'ix_user_resumes_user_id' not in existing_indexes:
        op.create_index('ix_user_resumes_user_id', 'user_resumes', ['user_id'], unique=False)
    if 'ix_user_resumes_template_id' not in existing_indexes:
        op.create_index('ix_user_resumes_template_id', 'user_resumes', ['template_id'], unique=False)
    if 'ix_user_resumes_created_at' not in existing_indexes:
        op.create_index('ix_user_resumes_created_at', 'user_resumes', ['created_at'], unique=False)
    if 'idx_resume_user_created' not in existing_indexes:
        op.create_index('idx_resume_user_created', 'user_resumes', ['user_id', 'created_at'], unique=False)
    
    # 为 ParsedResume 表添加索引
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('parsed_resumes')]
    if 'ix_parsed_resumes_user_id' not in existing_indexes:
        op.create_index('ix_parsed_resumes_user_id', 'parsed_resumes', ['user_id'], unique=False)
    if 'ix_parsed_resumes_file_hash' not in existing_indexes:
        op.create_index('ix_parsed_resumes_file_hash', 'parsed_resumes', ['file_hash'], unique=False)
    if 'ix_parsed_resumes_created_at' not in existing_indexes:
        op.create_index('ix_parsed_resumes_created_at', 'parsed_resumes', ['created_at'], unique=False)
    if 'idx_parsed_user_created' not in existing_indexes:
        op.create_index('idx_parsed_user_created', 'parsed_resumes', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    # 删除索引（按相反顺序）
    op.drop_index('idx_parsed_user_created', table_name='parsed_resumes')
    op.drop_index('ix_parsed_resumes_created_at', table_name='parsed_resumes')
    op.drop_index('ix_parsed_resumes_file_hash', table_name='parsed_resumes')
    op.drop_index('ix_parsed_resumes_user_id', table_name='parsed_resumes')
    
    op.drop_index('idx_resume_user_created', table_name='user_resumes')
    op.drop_index('ix_user_resumes_created_at', table_name='user_resumes')
    op.drop_index('ix_user_resumes_template_id', table_name='user_resumes')
    op.drop_index('ix_user_resumes_user_id', table_name='user_resumes')
    
    op.drop_index('ix_template_versions_created_at', table_name='template_versions')
    op.drop_index('ix_template_versions_template_id', table_name='template_versions')
    
    op.drop_index('idx_template_created_by_active', table_name='resume_templates')
    op.drop_index('idx_template_public_active', table_name='resume_templates')
    op.drop_index('ix_resume_templates_created_by', table_name='resume_templates')
    op.drop_index('ix_resume_templates_is_active', table_name='resume_templates')
    op.drop_index('ix_resume_templates_is_public', table_name='resume_templates')


