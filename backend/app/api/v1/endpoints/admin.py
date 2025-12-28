"""
管理后台API接口
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
from ....core.database import get_db
from ....core.permissions import require_admin, require_super_admin
from ....models.user import User
from ....models.registration_request import UserRegistrationRequest
from ....models.resume import ResumeTemplate
from ....schemas.user import UserResponse
from ....schemas.registration_request import (
    RegistrationRequestResponse,
    RegistrationRequestReview
)
from ....schemas.resume import TemplateResponse
from ....schemas.system_settings import (
    SystemSettingResponse,
    SystemSettingUpdate,
    SystemSettingCreate,
    LLMConfigTestRequest,
    LLMConfigTestResponse
)
from ....core.security import get_password_hash
from ....services.config_service import config_service
from ....models.system_settings import SystemSetting

router = APIRouter()

# ==================== 用户管理 ====================

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    user_type: Optional[str] = None,
    registration_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取用户列表（管理员）"""
    query = db.query(User)
    
    # 搜索过滤
    if search:
        query = query.filter(
            or_(
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
        )
    
    # 用户类型过滤
    if user_type:
        query = query.filter(User.user_type == user_type)
    
    # 注册状态过滤
    if registration_status:
        query = query.filter(User.registration_status == registration_status)
    
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return users

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取用户详情（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user

@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    update_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """更新用户状态（管理员）"""
    import logging
    logger = logging.getLogger(__name__)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 记录接收到的数据
    logger.info(f"[更新用户] 用户ID: {user_id}, 接收到的数据: {update_data}")
    
    # 处理各个字段
    if 'is_active' in update_data and update_data['is_active'] is not None:
        user.is_active = update_data['is_active']
    
    if 'user_type' in update_data and update_data['user_type'] is not None:
        user.user_type = update_data['user_type']
        # 如果设置为超级管理员或模板设计师，清除使用次数限制
        if update_data['user_type'] in ["super_admin", "template_designer"]:
            user.monthly_usage_limit = None
            logger.info(f"[更新用户] 用户类型改为管理员，清除使用次数限制")
    
    if 'subscription_plan' in update_data and update_data['subscription_plan'] is not None:
        user.subscription_plan = update_data['subscription_plan']
    
    # 处理使用次数限制
    if 'monthly_usage_limit' in update_data:
        monthly_usage_limit = update_data['monthly_usage_limit']
        # 只有普通用户才需要设置使用次数限制
        if user.user_type not in ["super_admin", "template_designer"]:
            if monthly_usage_limit is not None:
                user.monthly_usage_limit = monthly_usage_limit
                logger.info(f"[更新用户] 更新使用次数限制: {monthly_usage_limit}")
            # 如果 monthly_usage_limit 是 None，且用户是普通用户，不更新（保持原值）
        else:
            # 如果是管理员，忽略使用次数限制设置
            user.monthly_usage_limit = None
            logger.info(f"[更新用户] 用户是管理员，忽略使用次数限制设置")
    
    db.commit()
    db.refresh(user)
    logger.info(f"[更新用户] 更新完成，用户ID: {user_id}, 使用次数限制: {user.monthly_usage_limit}")
    return user

@router.post("/users/fix-usage-limits")
async def fix_usage_limits(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """批量修复未设置使用次数限制的普通用户（设置为默认值20）"""
    # 查找所有普通用户（非管理员）且 monthly_usage_limit 为 None 的用户
    users_to_fix = db.query(User).filter(
        User.user_type.in_(["trial_user", "premium_user"]),
        User.monthly_usage_limit.is_(None)
    ).all()
    
    fixed_count = 0
    for user in users_to_fix:
        user.monthly_usage_limit = 20
        fixed_count += 1
    
    db.commit()
    
    return {
        "message": f"已修复 {fixed_count} 个用户的使用次数限制",
        "fixed_count": fixed_count
    }

# ==================== 注册审核管理 ====================

@router.get("/registration-requests", response_model=List[RegistrationRequestResponse])
async def list_registration_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取注册申请列表（管理员）"""
    query = db.query(UserRegistrationRequest)
    
    if status:
        query = query.filter(UserRegistrationRequest.status == status)
    else:
        # 默认只显示待审核的
        query = query.filter(UserRegistrationRequest.status == "pending")
    
    requests = query.order_by(UserRegistrationRequest.created_at.desc()).offset(skip).limit(limit).all()
    return requests

@router.post("/registration-requests/{request_id}/review")
async def review_registration_request(
    request_id: int,
    review: RegistrationRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """审核注册申请"""
    request = db.query(UserRegistrationRequest).filter(
        UserRegistrationRequest.id == request_id
    ).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="申请不存在")
    
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="该申请已被审核")
    
    if review.status == "approved":
        # 批准：创建用户账户
        # 检查邮箱是否已存在
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="该邮箱已被注册")
        
        # 从review_notes中提取密码哈希（注册时临时存储的）
        hashed_password = None
        if request.review_notes and request.review_notes.startswith("PASSWORD_HASH:"):
            hashed_password = request.review_notes.replace("PASSWORD_HASH:", "")
        
        # 如果没有密码哈希，生成临时密码
        if not hashed_password:
            import secrets
            temp_password = secrets.token_urlsafe(16)
            hashed_password = get_password_hash(temp_password)
            # TODO: 发送邮件通知用户临时密码
        
        new_user = User(
            email=request.email,
            password_hash=hashed_password,
            full_name=request.full_name,
            user_type="trial_user",
            registration_status="approved",
            monthly_usage_limit=20,  # 试用用户默认20次，管理员可以在用户管理中提升上限
            current_month_usage=0,
            usage_reset_date=func.now() + timedelta(days=30),  # 30天后重置
            reviewed_by=current_user.id,
            reviewed_at=func.now()
        )
        db.add(new_user)
        db.flush()  # 获取新用户的ID
        
        # 更新申请记录
        request.status = "approved"
        request.reviewed_by = current_user.id
        request.reviewed_at = func.now()
        # 保留审核备注，但移除密码哈希
        final_notes = review.review_notes or ""
        if request.review_notes and request.review_notes.startswith("PASSWORD_HASH:"):
            if final_notes:
                request.review_notes = final_notes
            else:
                request.review_notes = None
        else:
            request.review_notes = final_notes
        request.user_id = new_user.id
        
        db.commit()
        db.refresh(new_user)
        
        # TODO: 发送邮件通知用户审核通过
        
        return {
            "message": "审核通过，用户账户已创建",
            "user": new_user
        }
    
    elif review.status == "rejected":
        # 拒绝：更新申请状态
        request.status = "rejected"
        request.reviewed_by = current_user.id
        request.reviewed_at = func.now()
        request.review_notes = review.review_notes
        
        db.commit()
        
        # TODO: 发送邮件通知用户审核被拒绝
        
        return {"message": "审核已拒绝"}
    
    else:
        raise HTTPException(status_code=400, detail="无效的审核状态")

# ==================== 模板管理 ====================

@router.put("/templates/{template_id}/publish")
async def publish_template(
    template_id: int,
    publish_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """发布/下架模板（管理员）"""
    template = db.query(ResumeTemplate).filter(ResumeTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 从请求体中获取 is_published 参数
    is_published = publish_data.get("is_published", True)
    
    # 使用 is_public 字段控制是否对普通用户可见
    template.is_public = is_published
    db.commit()
    db.refresh(template)
    
    return {
        "message": "模板已发布" if is_published else "模板已下架",
        "template": template
    }

@router.get("/templates", response_model=List[TemplateResponse])
async def list_all_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取所有模板列表（管理员，包括未发布的）"""
    query = db.query(ResumeTemplate).filter(ResumeTemplate.is_active == True)  # 过滤已删除的模板
    
    if is_public is not None:
        query = query.filter(ResumeTemplate.is_public == is_public)
    
    templates = query.order_by(ResumeTemplate.created_at.desc()).offset(skip).limit(limit).all()
    return templates

# ==================== 数据统计 ====================

@router.get("/statistics")
async def get_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取系统统计数据（管理员）"""
    # 用户统计
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    trial_users = db.query(User).filter(User.user_type == "trial_user").count()
    premium_users = db.query(User).filter(User.user_type == "premium_user").count()
    
    # 待审核申请
    pending_requests = db.query(UserRegistrationRequest).filter(
        UserRegistrationRequest.status == "pending"
    ).count()
    
    # 模板统计
    total_templates = db.query(ResumeTemplate).count()
    public_templates = db.query(ResumeTemplate).filter(ResumeTemplate.is_public == True).count()
    
    # 使用统计
    total_generated = db.query(func.sum(User.resume_generated_count)).scalar() or 0
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "trial": trial_users,
            "premium": premium_users
        },
        "registration_requests": {
            "pending": pending_requests
        },
        "templates": {
            "total": total_templates,
            "public": public_templates
        },
        "usage": {
            "total_generated": total_generated
        }
    }

# ==================== 系统配置管理 ====================

@router.get("/settings", response_model=dict)
async def get_all_settings(
    category: Optional[str] = Query(None, description="配置分类筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """获取所有系统配置（仅超级管理员）"""
    settings = config_service.get_all_settings(db, category=category)
    return settings

@router.get("/settings/{key}", response_model=SystemSettingResponse)
async def get_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """获取特定配置（仅超级管理员）"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(status_code=404, detail=f"配置 {key} 不存在")
    
    # 脱敏处理
    value = setting.value
    if setting.is_encrypted and value:
        try:
            decrypted = config_service._decrypt(value)
            if len(decrypted) > 8:
                value = decrypted[:4] + "****" + decrypted[-4:]
            else:
                value = "****"
        except:
            value = "****"
    
    return SystemSettingResponse(
        key=setting.key,
        value=value,
        category=setting.category,
        description=setting.description,
        is_encrypted=setting.is_encrypted,
        updated_by=setting.updated_by,
        updated_at=setting.updated_at
    )

@router.put("/settings/{key}", response_model=SystemSettingResponse)
async def update_setting(
    key: str,
    update_data: SystemSettingUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """更新系统配置（仅超级管理员）
    
    注意：如果传入的值是脱敏值（包含"****"），说明用户没有修改，应该跳过更新。
    但如果配置解密失败（值为"****"且is_encrypted=true），用户需要重新输入完整的API密钥。
    """
    # 判断是否需要加密（API密钥需要加密）
    is_encrypted = key.endswith(".api_key") or "secret" in key.lower()
    
    # 根据key自动设置category
    if key.startswith("llm."):
        category = "llm"
    elif key.startswith("email."):
        category = "email"
    else:
        category = "system"
    
    # 清理配置值（去除前后空格和换行符），特别是API密钥
    # 如果值为空字符串，允许清除配置
    cleaned_value = update_data.value.strip() if update_data.value else ""
    
    # 检查是否是脱敏值（包含"****"），如果是，说明用户没有修改，应该跳过更新
    # 但如果是解密失败的情况（值为"****"），用户需要重新输入完整的API密钥
    if cleaned_value and "****" in cleaned_value:
        # 检查数据库中是否存在配置且解密失败
        existing_setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if existing_setting and existing_setting.is_encrypted:
            # 尝试解密，如果失败，说明需要重新输入
            try:
                config_service._decrypt(existing_setting.value)
                # 解密成功，说明是正常的脱敏值，跳过更新
                logger.info(f"配置 {key} 值为脱敏值，跳过更新")
                # 返回当前配置的脱敏值
                decrypted = config_service._decrypt(existing_setting.value)
                if len(decrypted) > 8:
                    value = decrypted[:4] + "****" + decrypted[-4:]
                else:
                    value = "****"
                return SystemSettingResponse(
                    key=existing_setting.key,
                    value=value,
                    category=existing_setting.category,
                    description=existing_setting.description,
                    is_encrypted=existing_setting.is_encrypted,
                    updated_by=existing_setting.updated_by,
                    updated_at=existing_setting.updated_at
                )
            except Exception as e:
                # 解密失败，说明配置已损坏，需要用户重新输入完整的API密钥
                logger.warning(f"配置 {key} 解密失败，但用户传入的是脱敏值。需要用户重新输入完整的API密钥: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"配置 {key} 无法解密（加密密钥已变化）。请重新输入完整的API密钥并保存，不要使用脱敏值。"
                )
        else:
            # 配置不存在或未加密，跳过更新
            logger.info(f"配置 {key} 值为脱敏值，跳过更新")
            if existing_setting:
                # 返回当前配置
                value = existing_setting.value
                if existing_setting.is_encrypted and value:
                    try:
                        decrypted = config_service._decrypt(value)
                        if len(decrypted) > 8:
                            value = decrypted[:4] + "****" + decrypted[-4:]
                        else:
                            value = "****"
                    except:
                        value = "****"
                return SystemSettingResponse(
                    key=existing_setting.key,
                    value=value,
                    category=existing_setting.category,
                    description=existing_setting.description,
                    is_encrypted=existing_setting.is_encrypted,
                    updated_by=existing_setting.updated_by,
                    updated_at=existing_setting.updated_at
                )
            else:
                # 配置不存在，返回空值
                return SystemSettingResponse(
                    key=key,
                    value="",
                    category=category,
                    description=update_data.description or "",
                    is_encrypted=is_encrypted,
                    updated_by=current_user.id,
                    updated_at=datetime.utcnow()
                )
    
    # 如果值为空字符串，删除配置（清除密钥）
    if cleaned_value == "":
        existing_setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if existing_setting:
            db.delete(existing_setting)
            db.commit()
            config_service.clear_cache(key)
            logger.info(f"配置 {key} 已删除（清除密钥）")
            # 返回一个表示已删除的响应
            return SystemSettingResponse(
                key=key,
                value="",
                category=category,
                description=update_data.description or "",
                is_encrypted=is_encrypted,
                updated_by=current_user.id,
                updated_at=datetime.utcnow()
            )
        else:
            # 配置不存在，直接返回空值
            return SystemSettingResponse(
                key=key,
                value="",
                category=category,
                description=update_data.description or "",
                is_encrypted=is_encrypted,
                updated_by=current_user.id,
                updated_at=datetime.utcnow()
            )
    
    setting = config_service.set_setting(
        db=db,
        key=key,
        value=cleaned_value,
        category=category,
        is_encrypted=is_encrypted,
        updated_by=current_user.id,
        description=update_data.description
    )
    
    # 清除缓存
    config_service.clear_cache(key)
    
    # 返回脱敏后的值
    value = setting.value
    if setting.is_encrypted and value:
        try:
            decrypted = config_service._decrypt(value)
            if len(decrypted) > 8:
                value = decrypted[:4] + "****" + decrypted[-4:]
            else:
                value = "****"
        except:
            value = "****"
    
    return SystemSettingResponse(
        key=setting.key,
        value=value,
        category=setting.category,
        description=setting.description,
        is_encrypted=setting.is_encrypted,
        updated_by=setting.updated_by,
        updated_at=setting.updated_at
    )

@router.post("/settings", response_model=SystemSettingResponse)
async def create_setting(
    create_data: SystemSettingCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """创建系统配置（仅超级管理员）"""
    # 检查是否已存在
    existing = db.query(SystemSetting).filter(SystemSetting.key == create_data.key).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"配置 {create_data.key} 已存在，请使用PUT方法更新")
    
    # 根据key自动设置category（如果未指定或使用默认值）
    category = create_data.category
    if category == "system" and create_data.key.startswith("llm."):
        category = "llm"
    elif category == "system" and create_data.key.startswith("email."):
        category = "email"
    
    setting = config_service.set_setting(
        db=db,
        key=create_data.key,
        value=create_data.value,
        category=category,
        description=create_data.description,
        is_encrypted=create_data.is_encrypted,
        updated_by=current_user.id
    )
    
    # 返回脱敏后的值
    value = setting.value
    if setting.is_encrypted and value:
        try:
            decrypted = config_service._decrypt(value)
            if len(decrypted) > 8:
                value = decrypted[:4] + "****" + decrypted[-4:]
            else:
                value = "****"
        except:
            value = "****"
    
    return SystemSettingResponse(
        key=setting.key,
        value=value,
        category=setting.category,
        description=setting.description,
        is_encrypted=setting.is_encrypted,
        updated_by=setting.updated_by,
        updated_at=setting.updated_at
    )

@router.post("/settings/test-llm-connection", response_model=LLMConfigTestResponse)
async def test_llm_connection(
    test_data: LLMConfigTestRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """测试LLM API连接（仅超级管理员）"""
    import httpx
    
    try:
        # 清理API密钥（去除前后空格和换行符）
        api_key = test_data.api_key.strip() if test_data.api_key else ""
        
        # 根据provider选择配置
        if test_data.provider == "deepseek":
            # 优先从数据库读取真实密钥（不管前端发送什么）
            # 如果前端发送的是完整的API密钥（长度>=20且不包含"****"），优先使用前端值
            # 否则，从数据库读取
            if api_key and len(api_key) >= 20 and "****" not in api_key:
                # 前端发送了完整的新密钥，直接使用
                logger.info(f"[测试连接] 使用前端发送的完整API密钥（长度: {len(api_key)}）")
            else:
                # 前端发送的是脱敏值、空值或短值，从数据库读取
                logger.info(f"[测试连接] 前端发送的值不可用（长度: {len(api_key)}），尝试从数据库读取真实API密钥")
                # 清除缓存，确保读取最新值
                config_service.clear_cache("llm.deepseek.api_key")
                db_api_key = config_service.get_setting(db, "llm.deepseek.api_key")
                if db_api_key and db_api_key.strip():
                    api_key = db_api_key.strip()
                    logger.info(f"[测试连接] 从数据库成功读取API密钥，长度: {len(api_key)}")
                else:
                    # 数据库中没有配置或解密失败
                    logger.warning(f"[测试连接] 无法从数据库读取API密钥，配置可能不存在或解密失败。尝试检查数据库记录...")
                    # 尝试直接查询数据库，看看配置是否存在
                    from ....models.system_settings import SystemSetting
                    db_setting = db.query(SystemSetting).filter(SystemSetting.key == "llm.deepseek.api_key").first()
                    if db_setting:
                        logger.warning(f"[测试连接] 数据库中存在配置记录，但解密失败。is_encrypted={db_setting.is_encrypted}, value_length={len(db_setting.value) if db_setting.value else 0}")
                        # 如果解密失败，可能是加密密钥发生了变化，需要重新保存配置
                        return LLMConfigTestResponse(
                            success=False,
                            message="检测到已保存的配置，但无法解密（可能是加密密钥已变化）。请在前端表单中重新输入完整的API密钥并保存，然后再测试连接。",
                            provider=test_data.provider
                        )
                    else:
                        logger.warning(f"[测试连接] 数据库中不存在配置记录")
                        return LLMConfigTestResponse(
                            success=False,
                            message="无法从数据库读取API密钥。请在前端表单中输入完整的API密钥并保存，然后再测试连接。",
                            provider=test_data.provider
                        )
            
            # 验证API密钥不为空（移除了之前的空值检查，因为现在优先从数据库读取）
            if not api_key or not api_key.strip():
                return LLMConfigTestResponse(
                    success=False,
                    message="API密钥不能为空，请在前端表单中输入API密钥或确保数据库中已保存配置",
                    provider=test_data.provider
                )
            
            base_url = (test_data.base_url or "https://api.deepseek.com/v1").strip()
            model_name = test_data.model_name or "deepseek-chat"
            # 确保base_url以/chat/completions结尾
            if not base_url.endswith("/chat/completions"):
                if not base_url.endswith("/"):
                    base_url += "/"
                base_url += "chat/completions"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"[测试连接] DeepSeek - API密钥长度: {len(api_key)}, 前缀: {api_key[:4]}..., Base URL: {base_url}, Model: {model_name}")
            
        elif test_data.provider == "doubao":
            # 优先从数据库读取真实密钥（不管前端发送什么）
            # 如果前端发送的是完整的API密钥（长度>=20且不包含"****"），优先使用前端值
            # 否则，从数据库读取
            if api_key and len(api_key) >= 20 and "****" not in api_key:
                # 前端发送了完整的新密钥，直接使用
                logger.info(f"[测试连接] 使用前端发送的完整API密钥（长度: {len(api_key)}）")
            else:
                # 前端发送的是脱敏值、空值或短值，从数据库读取
                logger.info(f"[测试连接] 前端发送的值不可用（长度: {len(api_key)}），尝试从数据库读取真实API密钥")
                # 清除缓存，确保读取最新值
                config_service.clear_cache("llm.doubao.api_key")
                db_api_key = config_service.get_setting(db, "llm.doubao.api_key")
                if db_api_key and db_api_key.strip():
                    api_key = db_api_key.strip()
                    logger.info(f"[测试连接] 从数据库成功读取API密钥，长度: {len(api_key)}")
                else:
                    # 数据库中没有配置或解密失败
                    logger.warning(f"[测试连接] 无法从数据库读取API密钥，配置可能不存在或解密失败。尝试检查数据库记录...")
                    # 尝试直接查询数据库，看看配置是否存在
                    from ....models.system_settings import SystemSetting
                    db_setting = db.query(SystemSetting).filter(SystemSetting.key == "llm.doubao.api_key").first()
                    if db_setting:
                        logger.warning(f"[测试连接] 数据库中存在配置记录，但解密失败。is_encrypted={db_setting.is_encrypted}, value_length={len(db_setting.value) if db_setting.value else 0}")
                        # 如果解密失败，可能是加密密钥发生了变化，需要重新保存配置
                        return LLMConfigTestResponse(
                            success=False,
                            message="检测到已保存的配置，但无法解密（可能是加密密钥已变化）。请在前端表单中重新输入完整的API密钥并保存，然后再测试连接。",
                            provider=test_data.provider
                        )
                    else:
                        logger.warning(f"[测试连接] 数据库中不存在配置记录")
                        return LLMConfigTestResponse(
                            success=False,
                            message="无法从数据库读取API密钥。请在前端表单中输入完整的API密钥并保存，然后再测试连接。",
                            provider=test_data.provider
                        )
            
            # 验证API密钥不为空（移除了之前的空值检查，因为现在优先从数据库读取）
            if not api_key or not api_key.strip():
                return LLMConfigTestResponse(
                    success=False,
                    message="API密钥不能为空，请在前端表单中输入API密钥或确保数据库中已保存配置",
                    provider=test_data.provider
                )
            
            base_url = (test_data.base_url or "https://ark.cn-beijing.volces.com/api/v3/chat/completions").strip()
            model_name = test_data.model_name or "doubao-seed-1-6-lite-251015"
            # 豆包的base_url已经包含完整路径，不需要再添加/chat/completions
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"[测试连接] 豆包 - API密钥长度: {len(api_key)}, 前缀: {api_key[:4]}..., Base URL: {base_url}, Model: {model_name}")
            
        elif test_data.provider == "qwen":
            # 优先从数据库读取真实密钥（不管前端发送什么）
            # 如果前端发送的是完整的API密钥（长度>=20且不包含"****"），优先使用前端值
            # 否则，从数据库读取
            if api_key and len(api_key) >= 20 and "****" not in api_key:
                # 前端发送了完整的新密钥，直接使用
                logger.info(f"[测试连接] 使用前端发送的完整API密钥（长度: {len(api_key)}）")
            else:
                # 前端发送的是脱敏值、空值或短值，从数据库读取
                logger.info(f"[测试连接] 前端发送的值不可用（长度: {len(api_key)}），尝试从数据库读取真实API密钥")
                # 清除缓存，确保读取最新值
                config_service.clear_cache("llm.qwen.api_key")
                db_api_key = config_service.get_setting(db, "llm.qwen.api_key")
                if db_api_key and db_api_key.strip():
                    api_key = db_api_key.strip()
                    logger.info(f"[测试连接] 从数据库成功读取API密钥，长度: {len(api_key)}")
                else:
                    # 数据库中没有配置或解密失败
                    logger.warning(f"[测试连接] 无法从数据库读取API密钥，配置可能不存在或解密失败。尝试检查数据库记录...")
                    # 尝试直接查询数据库，看看配置是否存在
                    from ....models.system_settings import SystemSetting
                    db_setting = db.query(SystemSetting).filter(SystemSetting.key == "llm.qwen.api_key").first()
                    if db_setting:
                        logger.warning(f"[测试连接] 数据库中存在配置记录，但解密失败。is_encrypted={db_setting.is_encrypted}, value_length={len(db_setting.value) if db_setting.value else 0}")
                        # 如果解密失败，可能是加密密钥发生了变化，需要重新保存配置
                        return LLMConfigTestResponse(
                            success=False,
                            message="检测到已保存的配置，但无法解密（可能是加密密钥已变化）。请在前端表单中重新输入完整的API密钥并保存，然后再测试连接。",
                            provider=test_data.provider
                        )
                    else:
                        logger.warning(f"[测试连接] 数据库中不存在配置记录")
                        return LLMConfigTestResponse(
                            success=False,
                            message="无法从数据库读取API密钥。请在前端表单中输入完整的API密钥并保存，然后再测试连接。",
                            provider=test_data.provider
                        )
            
            # 验证API密钥不为空
            if not api_key or not api_key.strip():
                return LLMConfigTestResponse(
                    success=False,
                    message="API密钥不能为空，请在前端表单中输入API密钥或确保数据库中已保存配置",
                    provider=test_data.provider
                )
            
            base_url = (test_data.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
            model_name = test_data.model_name or "qwen3-next-80b-a3b-instruct"
            # 确保base_url以/chat/completions结尾
            if not base_url.endswith("/chat/completions"):
                if not base_url.endswith("/"):
                    base_url += "/"
                base_url += "chat/completions"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"[测试连接] 千问 - API密钥长度: {len(api_key)}, 前缀: {api_key[:4]}..., Base URL: {base_url}, Model: {model_name}")
            
        else:
            return LLMConfigTestResponse(
                success=False,
                message=f"不支持的服务商: {test_data.provider}",
                provider=test_data.provider
            )
        
        # 发送一个简单的测试请求
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                base_url,
                headers=headers,
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 5
                }
            )
            
            if response.status_code == 200:
                logger.info(f"[测试连接] {test_data.provider} API密钥验证成功")
                return LLMConfigTestResponse(
                    success=True,
                    message="API密钥验证成功",
                    provider=test_data.provider
                )
            elif response.status_code == 401:
                # 尝试获取更详细的错误信息
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "API密钥无效或已过期")
                    logger.warning(f"[测试连接] {test_data.provider} API密钥验证失败: {error_msg}")
                except:
                    error_msg = "API密钥无效或已过期"
                    logger.warning(f"[测试连接] {test_data.provider} API密钥验证失败: 401 Unauthorized")
                
                return LLMConfigTestResponse(
                    success=False,
                    message=f"API密钥无效或已过期: {error_msg}",
                    provider=test_data.provider
                )
            elif response.status_code == 429:
                return LLMConfigTestResponse(
                    success=False,
                    message="API调用频率限制，请稍后重试",
                    provider=test_data.provider
                )
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                except:
                    error_msg = f"HTTP {response.status_code}"
                return LLMConfigTestResponse(
                    success=False,
                    message=f"API调用失败: {error_msg}",
                    provider=test_data.provider
                )
    except httpx.TimeoutException:
        return LLMConfigTestResponse(
            success=False,
            message="连接超时，请检查网络或API地址",
            provider=test_data.provider
        )
    except Exception as e:
        return LLMConfigTestResponse(
            success=False,
            message=f"测试失败: {str(e)}",
            provider=test_data.provider
        )

