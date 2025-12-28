"""rename_user_resumes_to_candidate_resumes_and_add_fields

Revision ID: 51500ac153d3
Revises: 293b19959363
Create Date: 2025-12-04 11:44:31.476314

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '51500ac153d3'
down_revision = '293b19959363'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 检查表是否存在，如果不存在则重命名
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    tables = inspector.get_table_names()
    
    # 1. 重命名表 user_resumes -> candidate_resumes（如果表还存在）
    if 'user_resumes' in tables and 'candidate_resumes' not in tables:
        op.rename_table('user_resumes', 'candidate_resumes')
    elif 'candidate_resumes' not in tables:
        # 如果两个表都不存在，说明可能是新数据库，跳过重命名
        pass
    
    # 检查 candidate_resumes 表的列
    if 'candidate_resumes' in tables:
        columns = [col['name'] for col in inspector.get_columns('candidate_resumes')]
        
        # 2. 添加新字段（如果不存在）
        if 'parsed_resume_id' not in columns:
            op.add_column('candidate_resumes', sa.Column('parsed_resume_id', sa.Integer(), nullable=True))
        if 'candidate_name' not in columns:
            op.add_column('candidate_resumes', sa.Column('candidate_name', sa.String(length=255), nullable=True))
    
    # 3. 添加外键约束（如果不存在）
    if 'candidate_resumes' in tables:
        foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys('candidate_resumes')]
        if 'fk_candidate_resumes_parsed_resume_id' not in foreign_keys:
            op.create_foreign_key(
                'fk_candidate_resumes_parsed_resume_id',
                'candidate_resumes',
                'parsed_resumes',
                ['parsed_resume_id'],
                ['id'],
                ondelete='SET NULL'
            )
        
        # 4. 创建索引（如果不存在）
        indexes = [idx['name'] for idx in inspector.get_indexes('candidate_resumes')]
        if 'ix_candidate_resumes_parsed_resume_id' not in indexes:
            op.create_index('ix_candidate_resumes_parsed_resume_id', 'candidate_resumes', ['parsed_resume_id'], unique=False)
        
        # 5. 更新复合索引名称
        if 'idx_resume_user_created' in indexes:
            op.drop_index('idx_resume_user_created', table_name='candidate_resumes')
        if 'idx_candidate_resume_user_created' not in indexes:
            op.create_index('idx_candidate_resume_user_created', 'candidate_resumes', ['user_id', 'created_at'], unique=False)
    
    # 6. 创建 source_files 表（如果不存在）
    if 'source_files' not in tables:
        op.create_table('source_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_type', sa.String(length=100), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
        # 创建索引（如果不存在）
        source_file_indexes = [idx['name'] for idx in inspector.get_indexes('source_files')] if 'source_files' in tables else []
        if 'ix_source_files_id' not in source_file_indexes:
            op.create_index('ix_source_files_id', 'source_files', ['id'], unique=False)
        if 'ix_source_files_user_id' not in source_file_indexes:
            op.create_index('ix_source_files_user_id', 'source_files', ['user_id'], unique=False)
        if 'ix_source_files_file_hash' not in source_file_indexes:
            op.create_index('ix_source_files_file_hash', 'source_files', ['file_hash'], unique=False)
    else:
        # 如果表已存在，检查并创建缺失的索引
        source_file_indexes = [idx['name'] for idx in inspector.get_indexes('source_files')]
        if 'ix_source_files_id' not in source_file_indexes:
            op.create_index('ix_source_files_id', 'source_files', ['id'], unique=False)
        if 'ix_source_files_user_id' not in source_file_indexes:
            op.create_index('ix_source_files_user_id', 'source_files', ['user_id'], unique=False)
        if 'ix_source_files_file_hash' not in source_file_indexes:
            op.create_index('ix_source_files_file_hash', 'source_files', ['file_hash'], unique=False)
    
    # 7. 为 ParsedResume 添加 source_file_path 和 candidate_name 字段（如果还没有）
    if 'parsed_resumes' in tables:
        parsed_columns = [col['name'] for col in inspector.get_columns('parsed_resumes')]
        if 'source_file_path' not in parsed_columns:
            op.add_column('parsed_resumes', sa.Column('source_file_path', sa.String(length=500), nullable=True))
        if 'candidate_name' not in parsed_columns:
            op.add_column('parsed_resumes', sa.Column('candidate_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    # 1. 删除 source_files 表
    op.drop_index('ix_source_files_file_hash', table_name='source_files')
    op.drop_index('ix_source_files_user_id', table_name='source_files')
    op.drop_index('ix_source_files_id', table_name='source_files')
    op.drop_table('source_files')
    
    # 2. 删除 ParsedResume 的新字段
    try:
        op.drop_column('parsed_resumes', 'candidate_name')
    except:
        pass
    try:
        op.drop_column('parsed_resumes', 'source_file_path')
    except:
        pass
    
    # 3. 恢复复合索引名称
    op.drop_index('idx_candidate_resume_user_created', table_name='candidate_resumes')
    op.create_index('idx_resume_user_created', 'candidate_resumes', ['user_id', 'created_at'], unique=False)
    
    # 4. 删除索引和外键
    op.drop_index('ix_candidate_resumes_parsed_resume_id', table_name='candidate_resumes')
    op.drop_constraint('fk_candidate_resumes_parsed_resume_id', 'candidate_resumes', type_='foreignkey')
    
    # 5. 删除新字段
    op.drop_column('candidate_resumes', 'candidate_name')
    op.drop_column('candidate_resumes', 'parsed_resume_id')
    
    # 6. 重命名表回 user_resumes
    op.rename_table('candidate_resumes', 'user_resumes')


