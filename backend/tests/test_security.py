"""
安全功能测试
"""
import pytest
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_email_from_token
)


class TestPasswordHashing:
    """密码哈希测试"""
    
    def test_hash_password(self):
        """测试密码哈希生成"""
        password = "Test123456!"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    
    def test_verify_password_correct(self):
        """测试正确密码验证"""
        password = "Test123456!"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """测试错误密码验证"""
        password = "Test123456!"
        wrong_password = "WrongPassword123!"
        hashed = get_password_hash(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty(self):
        """测试空密码验证"""
        password = ""
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
        assert verify_password("wrong", hashed) is False


class TestJWTToken:
    """JWT Token 测试"""
    
    def test_create_token(self):
        """测试创建 token"""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_get_email_from_token(self):
        """测试从 token 获取邮箱"""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        
        email = get_email_from_token(token)
        assert email == "test@example.com"
    
    def test_get_email_from_invalid_token(self):
        """测试无效 token"""
        invalid_token = "invalid.token.here"
        email = get_email_from_token(invalid_token)
        
        assert email is None

