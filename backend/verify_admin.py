"""验证管理员账户"""
from app.core.database import SessionLocal
from app.models.user import User
import bcrypt

def verify_admin(email: str, password: str):
    """验证管理员账户"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ 用户 {email} 不存在")
            return False
        
        print("=" * 50)
        print("账户信息:")
        print("=" * 50)
        print(f"ID: {user.id}")
        print(f"邮箱: {user.email}")
        print(f"姓名: {user.full_name}")
        print(f"用户类型: {user.user_type}")
        print(f"审核状态: {user.registration_status}")
        print(f"账户状态: {'启用' if user.is_active else '禁用'}")
        print(f"每月使用限制: {user.monthly_usage_limit}")
        print("=" * 50)
        
        # 验证密码
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        stored_hash = user.password_hash.encode('utf-8')
        if bcrypt.checkpw(password_bytes, stored_hash):
            print("✅ 密码验证成功！")
            print("=" * 50)
            return True
        else:
            print("❌ 密码验证失败！")
            print("=" * 50)
            return False
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "Admin123456"
    verify_admin(email, password)

