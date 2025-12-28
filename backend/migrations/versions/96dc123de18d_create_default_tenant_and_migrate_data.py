"""create_default_tenant_and_migrate_data

Revision ID: 96dc123de18d
Revises: d449f438bceb
Create Date: 2025-12-25 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '96dc123de18d'
down_revision = 'd449f438bceb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    创建默认租户并为现有用户和数据分配tenant_id
    """
    # 创建默认租户
    tenants_table = table(
        'tenants',
        column('id', sa.Integer),
        column('name', sa.String),
        column('domain', sa.String),
        column('contact_email', sa.String),
        column('contact_phone', sa.String),
        column('subscription_plan', sa.String),
        column('subscription_start', sa.DateTime),
        column('subscription_end', sa.DateTime),
        column('status', sa.String),
        column('max_users', sa.Integer),
        column('max_jobs', sa.Integer),
        column('max_resumes_per_month', sa.Integer),
        column('current_month_resume_count', sa.Integer),
        column('created_at', sa.DateTime),
        column('updated_at', sa.DateTime)
    )
    
    # 插入默认租户
    op.execute(
        tenants_table.insert().values(
            name='默认租户',
            domain=None,
            contact_email=None,
            contact_phone=None,
            subscription_plan='trial',
            subscription_start=datetime.utcnow(),
            subscription_end=None,
            status='active',
            max_users=10,
            max_jobs=20,
            max_resumes_per_month=200,
            current_month_resume_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    )
    
    # 获取默认租户ID（假设是1，因为这是第一个插入的记录）
    # 注意：在实际执行时，我们需要查询获取ID，但Alembic迁移中不能直接查询
    # 所以这里使用固定值1，如果迁移失败，可以手动调整
    
    # 为现有用户分配默认租户（tenant_id=1）
    # 注意：平台管理员（user_type='super_admin'或'platform_admin'）保持tenant_id为None
    op.execute("""
        UPDATE users 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL 
        AND user_type NOT IN ('super_admin', 'platform_admin')
    """)
    
    # 为现有数据分配默认租户（tenant_id=1）
    # 注意：这些数据属于现有用户，所以应该属于默认租户
    
    # job_positions表
    op.execute("""
        UPDATE job_positions 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL
    """)
    
    # filter_rules表
    op.execute("""
        UPDATE filter_rules 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL
    """)
    
    # resume_job_matches表
    op.execute("""
        UPDATE resume_job_matches 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL
    """)
    
    # company_info表
    op.execute("""
        UPDATE company_info 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL
    """)
    
    # match_models表
    op.execute("""
        UPDATE match_models 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL
    """)
    
    # candidate_resumes表
    op.execute("""
        UPDATE candidate_resumes 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL
    """)
    
    # resume_templates表（注意：平台公共模板保持tenant_id为None）
    # 这里只更新明确属于用户的模板
    op.execute("""
        UPDATE resume_templates 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL 
        AND is_public = false
    """)
    
    # source_files表
    op.execute("""
        UPDATE source_files 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL
    """)
    
    # parsed_resumes表
    op.execute("""
        UPDATE parsed_resumes 
        SET tenant_id = 1 
        WHERE tenant_id IS NULL
    """)


def downgrade() -> None:
    """
    回滚：将所有tenant_id设置为NULL，并删除默认租户
    """
    # 将所有数据的tenant_id设置为NULL
    op.execute("UPDATE users SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE job_positions SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE filter_rules SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE resume_job_matches SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE company_info SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE match_models SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE candidate_resumes SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE resume_templates SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE source_files SET tenant_id = NULL WHERE tenant_id = 1")
    op.execute("UPDATE parsed_resumes SET tenant_id = NULL WHERE tenant_id = 1")
    
    # 删除默认租户
    op.execute("DELETE FROM tenants WHERE id = 1")
