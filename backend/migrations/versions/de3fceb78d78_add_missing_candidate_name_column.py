"""add_missing_candidate_name_column

Revision ID: de3fceb78d78
Revises: 51500ac153d3
Create Date: 2025-12-04 12:40:59.093557

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'de3fceb78d78'
down_revision = '51500ac153d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 检查 candidate_resumes 表是否存在 candidate_name 字段
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    tables = inspector.get_table_names()
    
    if 'candidate_resumes' in tables:
        columns = [col['name'] for col in inspector.get_columns('candidate_resumes')]
        if 'candidate_name' not in columns:
            op.add_column('candidate_resumes', sa.Column('candidate_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    # 删除 candidate_name 字段
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    tables = inspector.get_table_names()
    
    if 'candidate_resumes' in tables:
        columns = [col['name'] for col in inspector.get_columns('candidate_resumes')]
        if 'candidate_name' in columns:
            op.drop_column('candidate_resumes', 'candidate_name')


