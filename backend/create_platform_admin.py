"""
创建或更新平台管理员账号
"""
from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def create_platform_admin():
    """创建或更新平台管理员账号"""
    db = SessionLocal()
    try:
        # 检查 admin@example.com
        admin = db.query(User).filter(User.email == 'admin@example.com').first()
        
        if admin:
            # 更新现有账号
            admin.role = 'platform_admin'
            admin.user_type = 'super_admin'
            admin.tenant_id = None  # 平台管理员没有租户
            admin.is_active = True
            admin.is_verified = True
            admin.registration_status = 'approved'
            # 如果密码不是 Admin123456，则更新
            from app.core.security import verify_password
            if not verify_password('Admin123456', admin.password_hash):
                admin.password_hash = get_password_hash('Admin123456')
            print(f"已更新平台管理员: admin@example.com")
            print(f"  密码: Admin123456")
            print(f"  role: {admin.role}")
            print(f"  user_type: {admin.user_type}")
        else:
            # 创建新账号
            admin = User(
                email='admin@example.com',
                password_hash=get_password_hash('Admin123456'),
                full_name='平台管理员',
                role='platform_admin',
                user_type='super_admin',
                tenant_id=None,
                is_active=True,
                is_verified=True,
                registration_status='approved'
            )
            db.add(admin)
            print(f"已创建平台管理员: admin@example.com")
            print(f"  密码: Admin123456")
        
        db.commit()
        print("\n平台管理员账号信息:")
        print("  邮箱: admin@example.com")
        print("  密码: Admin123456")
        print("  角色: platform_admin")
        print("  用户类型: super_admin")
        
    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_platform_admin()

