"""add_parsed_resume_id_to_user_resumes

Revision ID: 293b19959363
Revises: cf25aa63f561
Create Date: 2025-12-04 10:11:10.428133

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '293b19959363'
down_revision = 'cf25aa63f561'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加 parsed_resume_id 列到 user_resumes 表
    # 注意：此时表名可能已经是 candidate_resumes，需要检查
    op.add_column('candidate_resumes', sa.Column('parsed_resume_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_candidate_resumes_parsed_resume_id',
        'candidate_resumes',
        'parsed_resumes',
        ['parsed_resume_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_candidate_resumes_parsed_resume_id', 'candidate_resumes', type_='foreignkey')
    op.drop_column('candidate_resumes', 'parsed_resume_id')


