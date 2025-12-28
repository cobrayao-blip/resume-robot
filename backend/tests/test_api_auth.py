"""
API 认证测试
"""
import pytest
from fastapi.testclient import TestClient
from app.models.user import User
from app.core.security import get_password_hash


class TestAuthAPI:
    """认证 API 测试"""
    
    def test_register_success(self, client, db_session):
        """测试注册成功"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "Test123456!",
                "full_name": "New User"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["email"] == "newuser@example.com"
    
    def test_register_duplicate_email(self, client, db_session):
        """测试重复邮箱注册"""
        # 第一次注册
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "Test123456!",
                "full_name": "User 1"
            }
        )
        
        # 第二次注册（应该失败）
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "Test123456!",
                "full_name": "User 2"
            }
        )
        
        assert response.status_code == 400
    
    def test_login_success(self, client, db_session):
        """测试登录成功"""
        # 先创建用户
        user = User(
            email="login@example.com",
            password_hash=get_password_hash("Test123456!"),
            full_name="Login User",
            user_type="trial_user",
            is_active=True,
            registration_status="approved",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # 登录
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "login@example.com",
                "password": "Test123456!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self, client, db_session):
        """测试错误密码登录"""
        # 先创建用户
        user = User(
            email="wrongpass@example.com",
            password_hash=get_password_hash("CorrectPassword123!"),
            full_name="Wrong Pass User",
            user_type="trial_user",
            is_active=True,
            registration_status="approved",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # 使用错误密码登录
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpass@example.com",
                "password": "WrongPassword123!"
            }
        )
        
        assert response.status_code == 401
    
    def test_login_inactive_user(self, client, db_session):
        """测试禁用用户登录"""
        # 创建禁用用户
        user = User(
            email="inactive@example.com",
            password_hash=get_password_hash("Test123456!"),
            full_name="Inactive User",
            user_type="trial_user",
            is_active=False,  # 禁用
            registration_status="approved",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # 尝试登录
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "inactive@example.com",
                "password": "Test123456!"
            }
        )
        
        assert response.status_code == 400
        assert "禁用" in response.json()["detail"]

