"""创建超级管理员账户"""
import sys
import os
import bcrypt
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.user import User
from sqlalchemy.sql import func

def create_admin(email: str, password: str, full_name: str = "超级管理员"):
    """创建超级管理员账户"""
    db: Session = SessionLocal()
    
    try:
        # 检查邮箱是否已存在
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"❌ 邮箱 {email} 已被注册")
            print(f"   用户ID: {existing_user.id}")
            print(f"   当前用户类型: {existing_user.user_type}")
            
            # 询问是否更新为管理员
            response = input(f"\n是否将现有用户更新为超级管理员？(y/n): ").strip().lower()
            if response == 'y':
                existing_user.user_type = 'super_admin'
                existing_user.registration_status = 'approved'
                existing_user.is_active = True
                existing_user.is_verified = True
                # 更新密码（直接使用bcrypt）
                password_bytes = password.encode('utf-8')
                if len(password_bytes) > 72:
                    password_bytes = password_bytes[:72]
                existing_user.password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
                db.commit()
                print(f"✅ 用户已更新为超级管理员")
                print(f"   邮箱: {email}")
                print(f"   密码: {password}")
                print(f"   用户类型: {existing_user.user_type}")
                return existing_user
            else:
                print("操作已取消")
                return None
        
        # 创建新管理员账户
        # 直接使用bcrypt哈希密码（避免passlib的兼容性问题）
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
        admin_user = User(
            email=email,
            password_hash=hashed_password,
            full_name=full_name,
            user_type='super_admin',
            subscription_plan='enterprise',
            registration_status='approved',
            is_active=True,
            is_verified=True,
            monthly_usage_limit=999999,  # 管理员无限制
            current_month_usage=0,
            usage_reset_date=func.now(),
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print("=" * 50)
        print("✅ 超级管理员账户创建成功！")
        print("=" * 50)
        print(f"邮箱: {email}")
        print(f"密码: {password}")
        print(f"姓名: {full_name}")
        print(f"用户类型: {admin_user.user_type}")
        print(f"用户ID: {admin_user.id}")
        print("=" * 50)
        print("\n⚠️  请妥善保管密码信息！")
        print("=" * 50)
        
        return admin_user
        
    except Exception as e:
        db.rollback()
        print(f"❌ 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 50)
    print("创建超级管理员账户")
    print("=" * 50)
    
    # 从命令行参数获取或提示输入
    if len(sys.argv) >= 3:
        email = sys.argv[1]
        password = sys.argv[2]
        full_name = sys.argv[3] if len(sys.argv) >= 4 else "超级管理员"
    else:
        email = input("请输入管理员邮箱: ").strip()
        password = input("请输入管理员密码: ").strip()
        full_name = input("请输入管理员姓名（可选，直接回车使用默认）: ").strip() or "超级管理员"
    
    if not email or not password:
        print("❌ 邮箱和密码不能为空")
        sys.exit(1)
    
    if len(password) < 6:
        print("❌ 密码至少6位")
        sys.exit(1)
    
    create_admin(email, password, full_name)

