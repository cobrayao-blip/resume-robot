from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from ....core.database import get_db
from ....core.security import verify_password, create_access_token, get_password_hash
from ....core.password_validator import validate_password_strength
from ....core.rate_limit import limiter, get_rate_limit
from ....models.user import User
from ....models.registration_request import UserRegistrationRequest
from ....schemas.user import UserCreate, UserResponse, Token, UserLogin
from ....schemas.registration_request import RegistrationRequestCreate, RegistrationRequestResponse
from sqlalchemy.sql import func

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

@router.post("/register", response_model=RegistrationRequestResponse)
@limiter.limit(get_rate_limit("register"))
async def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """
    用户注册 - 提交审核申请
    
    新用户注册需要提交审核申请，管理员审核通过后才能使用系统。
    
    **功能说明**:
    - 验证邮箱格式和密码强度
    - 检查邮箱是否已被注册
    - 创建注册申请记录（状态为pending）
    - 发送注册申请通知（TODO：待实现邮件通知）
    
    **请求参数**:
    ```json
    {
      "email": "user@example.com",
      "password": "SecurePass123!",
      "full_name": "张三"
    }
    ```
    
    **响应示例**:
    ```json
    {
      "id": 1,
      "email": "user@example.com",
      "full_name": "张三",
      "status": "pending",
      "created_at": "2025-12-09T10:00:00Z"
    }
    ```
    
    **错误响应**:
    - `400`: 邮箱已被注册或已有待审核申请
    - `422`: 请求参数验证失败（邮箱格式、密码强度等）
    - `429`: 请求过于频繁（速率限制）
    
    **密码要求**:
    - 长度至少8个字符
    - 包含大小写字母、数字和特殊字符
    - 不能是常见弱密码
    """
    # 检查邮箱是否已存在（用户表）
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 检查是否已有待审核的申请
    existing_request = db.query(UserRegistrationRequest).filter(
        UserRegistrationRequest.email == user_data.email,
        UserRegistrationRequest.status == "pending"
    ).first()
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已有待审核的注册申请，请等待审核"
        )
    
    # 验证密码强度
    is_valid, error_message = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    # 创建注册申请（不直接创建用户）
    # 注意：这里暂时保存密码哈希，审核通过后创建用户时使用
    # 实际应用中，可以考虑发送邮件让用户设置密码
    hashed_password = get_password_hash(user_data.password)
    
    registration_request = UserRegistrationRequest(
        email=user_data.email,
        full_name=user_data.full_name,
        status="pending"
    )
    
    # 将密码哈希临时存储在review_notes中（仅用于演示，生产环境应使用更安全的方式）
    # 实际应用中，审核通过后应发送邮件让用户设置密码
    registration_request.review_notes = f"PASSWORD_HASH:{hashed_password}"  # 临时存储
    
    db.add(registration_request)
    db.commit()
    db.refresh(registration_request)
    
    return registration_request

@router.post("/login", response_model=Token)
@limiter.limit(get_rate_limit("login"))
async def login(
    request: Request,
    body: UserLogin | None = Body(default=None, description="登录信息（JSON格式，支持email/username和password）"),
    db: Session = Depends(get_db)
):
    """
    用户登录
    
    支持 JSON 和表单两种格式的登录请求。
    
    **功能说明**:
    - 验证邮箱和密码
    - 检查用户账户状态（是否激活、是否通过审核）
    - 生成 JWT Token（有效期30分钟，可通过配置调整）
    - 支持速率限制（防止暴力破解）
    
    **请求格式**:
    
    JSON格式:
    ```json
    {
      "email": "user@example.com",
      "password": "SecurePass123!"
    }
    ```
    
    表单格式:
    ```
    email=user@example.com&password=SecurePass123!
    ```
    
    **响应示例**:
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer"
    }
    ```
    
    **错误响应**:
    - `401`: 邮箱或密码错误
    - `400`: 账户已被禁用或未通过审核
    - `422`: 请求参数验证失败
    - `429`: 请求过于频繁（速率限制）
    
    **Token 使用**:
    在后续请求的 Header 中添加：
    ```
    Authorization: Bearer <access_token>
    ```
    """
    # 兼容 JSON 与表单
    email = None
    password = None
    
    # 优先尝试从 Pydantic body 获取（FastAPI 自动解析的 JSON）
    if body is not None:
        try:
            if hasattr(body, 'email') and hasattr(body, 'password'):
                email = body.email
                password = body.password
        except Exception:
            pass
    
    # 如果 body 为空或解析失败，尝试从表单获取
    if not email or not password:
        try:
            form = await request.form()
            email = form.get("username") or form.get("email")
            password = form.get("password")
        except Exception:
            pass

    if not email or not password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="缺少邮箱或密码")

    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码过长，最大72字符")

    # 验证用户
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账户已被禁用，请联系管理员！"
        )
    
    # 检查注册审核状态（如果用户有审核状态）
    # 注意：管理员账户（super_admin, template_designer, tenant_admin）不受此限制
    if hasattr(user, 'registration_status') and user.registration_status:
        # 管理员账户跳过审核状态检查
        if user.user_type in ['super_admin', 'template_designer', 'tenant_admin']:
            pass  # 管理员可以直接登录
        elif user.registration_status == "pending":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您的注册申请正在审核中，请等待管理员审核"
            )
        elif user.registration_status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您的注册申请已被拒绝，请联系管理员"
            )
    
    # 更新最后登录时间
    user.last_login = func.now()
    db.commit()
    
    # 创建访问令牌（包含tenant_id）
    token_data = {"sub": user.email}
    if hasattr(user, 'tenant_id') and user.tenant_id is not None:
        token_data["tenant_id"] = user.tenant_id
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    刷新访问令牌
    
    使用当前有效的token刷新获取新的token，延长会话时间。
    如果当前token已过期，将返回401错误。
    
    **功能说明**:
    - 验证当前token是否有效
    - 检查用户账户状态
    - 生成新的访问令牌（有效期30分钟）
    
    **响应示例**:
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "user": { ... }
    }
    ```
    """
    from ....core.security import get_email_from_token
    
    # 从请求头获取token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的授权头"
        )
    
    token = auth_header.replace("Bearer ", "")
    email = get_email_from_token(token)
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌或令牌已过期"
        )
    
    # 查询用户
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 检查用户账户状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账户已被禁用，请联系管理员！"
        )
    
    # 创建新的访问令牌（包含tenant_id）
    token_data = {"sub": user.email}
    if hasattr(user, 'tenant_id') and user.tenant_id is not None:
        token_data["tenant_id"] = user.tenant_id
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }