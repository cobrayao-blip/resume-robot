from passlib.context import CryptContext
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from .config import settings

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码，兼容bcrypt和passlib生成的哈希"""
    try:
        # 先尝试使用passlib验证
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # 如果passlib失败，直接使用bcrypt验证
        try:
            password_bytes = plain_password.encode('utf-8')
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            stored_hash = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, stored_hash)
        except Exception:
            return False

def get_password_hash(password: str) -> str:
    """生成密码哈希，优先使用passlib，失败则使用bcrypt"""
    try:
        return pwd_context.hash(password)
    except Exception:
        # 如果passlib失败，直接使用bcrypt
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def get_email_from_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: Optional[str] = payload.get("sub")
        return email
    except JWTError:
        return None

def get_tenant_id_from_token(token: str) -> Optional[int]:
    """从JWT Token中提取tenant_id"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        tenant_id = payload.get("tenant_id")
        if tenant_id is not None:
            return int(tenant_id)
        return None
    except (JWTError, ValueError, TypeError):
        return None