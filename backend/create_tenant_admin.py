"""
创建租户管理员测试账户
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.user import User
from app.models.tenant import Tenant
from app.core.security import get_password_hash
from datetime import datetime

def create_tenant_admin():
    """创建租户管理员测试账户"""
    db: Session = SessionLocal()
    
    try:
        # 1. 检查或创建测试租户
        tenant = db.query(Tenant).filter(Tenant.name == "测试租户").first()
        if not tenant:
            tenant = Tenant(
                name="测试租户",
                domain="test-tenant",
                contact_email="admin@test-tenant.com",
                contact_phone="13800138000",
                subscription_plan="trial",
                subscription_start=datetime.utcnow(),
                status="active",
                max_users=10,
                max_jobs=50,
                max_resumes_per_month=500
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"✅ 创建测试租户成功: id={tenant.id}, name={tenant.name}")
        else:
            print(f"ℹ️  测试租户已存在: id={tenant.id}, name={tenant.name}")
        
        # 2. 检查租户管理员是否已存在
        tenant_admin = db.query(User).filter(
            User.email == "tenant_admin@test-tenant.com",
            User.tenant_id == tenant.id
        ).first()
        
        if tenant_admin:
            # 更新密码和角色
            tenant_admin.password_hash = get_password_hash("admin123456")
            tenant_admin.role = "tenant_admin"
            tenant_admin.user_type = "tenant_admin"
            tenant_admin.is_active = True
            tenant_admin.is_verified = True
            tenant_admin.registration_status = "approved"  # 设置为已审核通过
            db.commit()
            print(f"✅ 更新租户管理员成功: id={tenant_admin.id}, email={tenant_admin.email}")
            print(f"   密码: admin123456")
            print(f"   租户ID: {tenant.id}")
            print(f"   角色: {tenant_admin.role}")
        else:
            # 创建新的租户管理员
            tenant_admin = User(
                email="tenant_admin@test-tenant.com",
                password_hash=get_password_hash("admin123456"),
                full_name="租户管理员",
                role="tenant_admin",
                user_type="tenant_admin",
                tenant_id=tenant.id,
                is_active=True,
                is_verified=True,
                registration_status="approved",  # 设置为已审核通过
                subscription_plan="trial"
            )
            db.add(tenant_admin)
            db.commit()
            db.refresh(tenant_admin)
            print(f"✅ 创建租户管理员成功: id={tenant_admin.id}, email={tenant_admin.email}")
            print(f"   密码: admin123456")
            print(f"   租户ID: {tenant.id}")
            print(f"   角色: {tenant_admin.role}")
        
        # 3. 可选：创建一个HR用户用于测试
        hr_user = db.query(User).filter(
            User.email == "hr_user@test-tenant.com",
            User.tenant_id == tenant.id
        ).first()
        
        if not hr_user:
            hr_user = User(
                email="hr_user@test-tenant.com",
                password_hash=get_password_hash("hr123456"),
                full_name="HR用户",
                role="hr_user",
                user_type="hr_user",
                tenant_id=tenant.id,
                is_active=True,
                is_verified=True,
                registration_status="approved",  # 设置为已审核通过
                subscription_plan="trial"
            )
            db.add(hr_user)
            db.commit()
            print(f"✅ 创建HR用户成功: id={hr_user.id}, email={hr_user.email}")
            print(f"   密码: hr123456")
        
        print("\n" + "="*50)
        print("测试账户信息：")
        print("="*50)
        print(f"租户管理员:")
        print(f"  邮箱: tenant_admin@test-tenant.com")
        print(f"  密码: admin123456")
        print(f"  租户ID: {tenant.id}")
        print(f"  租户名称: {tenant.name}")
        print(f"\nHR用户:")
        print(f"  邮箱: hr_user@test-tenant.com")
        print(f"  密码: hr123456")
        print(f"  租户ID: {tenant.id}")
        print("="*50)
        
    except Exception as e:
        db.rollback()
        print(f"❌ 创建失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_tenant_admin()

