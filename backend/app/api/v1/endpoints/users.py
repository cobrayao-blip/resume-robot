from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
import httpx
import logging
from ....core.database import get_db
from ....models.user import User
from ....models.user_llm_config import UserLLMConfig
from ....schemas.user import UserResponse, UserUpdate, LLMConfigUpdate, LLMConfigResponse, PasswordChange
from ....schemas.system_settings import LLMConfigTestRequest, LLMConfigTestResponse
from ....core.security import get_email_from_token

logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")  # 必需认证（默认auto_error=True）
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)  # 可选认证

# 先定义依赖函数
async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """获取当前用户（必需认证）"""
    email = get_email_from_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    
    # 检查用户账户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账户已被禁用，请联系管理员！"
        )
    
    return user

async def get_current_user_optional(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional)
) -> Optional[User]:
    """获取当前用户（可选认证，token无效时返回None）"""
    if not token:
        return None
    email = get_email_from_token(token)
    if not email:
        return None
    user = db.query(User).filter(User.email == email).first()
    
    # 如果用户存在但被禁用，返回None（可选认证不抛出异常）
    if user and not user.is_active:
        return None
    
    return user

@router.get("/me", response_model=UserResponse)
async def get_current_user_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ← 现在可以正常使用了
):
    try:
        # 确保返回的数据符合 UserResponse schema
        return current_user
    except Exception as e:
        logger.error(f"获取当前用户信息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户信息失败: {str(e)}"
        )

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 更新用户信息
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    if user_update.subscription_plan is not None:
        current_user.subscription_plan = user_update.subscription_plan
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.get("/me/llm-config", response_model=LLMConfigResponse)
async def get_my_llm_config(
    provider: Optional[str] = Query(None, description="可选参数：指定要查询的provider（deepseek/doubao/qwen）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的LLM配置
    
    如果指定了provider参数，返回该provider的配置（如果有）
    如果没有指定provider，返回当前配置的provider的配置
    """
    if provider:
        # 如果指定了provider，查询该provider的配置
        user_config = db.query(UserLLMConfig).filter(
            UserLLMConfig.user_id == current_user.id,
            UserLLMConfig.provider == provider.lower()
        ).first()
        
        if user_config:
            # 返回配置，但API密钥脱敏
            api_key = user_config.api_key
            if api_key and len(api_key) > 8:
                api_key = api_key[:4] + "****" + api_key[-4:]
            
            return LLMConfigResponse(
                provider=user_config.provider,
                api_key=api_key,
                base_url=user_config.base_url,
                model_name=user_config.model_name
            )
        else:
            # 该provider没有配置，返回空配置
            return LLMConfigResponse(
                provider=provider.lower(),
                api_key=None,
                base_url=None,
                model_name=None
            )
    else:
        # 如果没有指定provider，返回当前配置的provider的配置（保持向后兼容）
        user_config = db.query(UserLLMConfig).filter(UserLLMConfig.user_id == current_user.id).first()
        
        if user_config:
            # 返回配置，但API密钥脱敏
            api_key = user_config.api_key
            if api_key and len(api_key) > 8:
                api_key = api_key[:4] + "****" + api_key[-4:]
            
            return LLMConfigResponse(
                provider=user_config.provider,
                api_key=api_key,
                base_url=user_config.base_url,
                model_name=user_config.model_name
            )
        else:
            # 返回默认DeepSeek配置
            return LLMConfigResponse(
                provider="deepseek",
                api_key=None,
                base_url=None,
                model_name=None
            )

@router.put("/me/llm-config", response_model=LLMConfigResponse)
async def update_my_llm_config(
    config_update: LLMConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新当前用户的LLM配置"""
    user_config = db.query(UserLLMConfig).filter(UserLLMConfig.user_id == current_user.id).first()
    
    if user_config:
        # 更新现有配置
        if config_update.provider is not None:
            user_config.provider = config_update.provider
        if config_update.api_key is not None:
            user_config.api_key = config_update.api_key
        if config_update.base_url is not None:
            user_config.base_url = config_update.base_url
        if config_update.model_name is not None:
            user_config.model_name = config_update.model_name
    else:
        # 创建新配置
        user_config = UserLLMConfig(
            user_id=current_user.id,
            provider=config_update.provider or "deepseek",
            api_key=config_update.api_key,
            base_url=config_update.base_url,
            model_name=config_update.model_name
        )
        db.add(user_config)
    
    db.commit()
    db.refresh(user_config)
    
    # 返回配置，API密钥脱敏
    api_key = user_config.api_key
    if api_key and len(api_key) > 8:
        api_key = api_key[:4] + "****" + api_key[-4:]
    
    return LLMConfigResponse(
        provider=user_config.provider,
        api_key=api_key,
        base_url=user_config.base_url,
        model_name=user_config.model_name
    )

@router.post("/me/llm-config/test-connection", response_model=LLMConfigTestResponse)
async def test_my_llm_connection(
    test_data: LLMConfigTestRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """测试用户LLM API连接"""
    try:
        # 清理API密钥（去除前后空格和换行符）
        api_key = test_data.api_key.strip() if test_data.api_key else ""
        
        # 如果前端发送的是完整的API密钥（长度>=20且不包含"****"），使用前端值
        # 否则，从用户配置中读取
        if not api_key or len(api_key) < 20 or "****" in api_key:
            # 从用户配置中读取
            user_config = db.query(UserLLMConfig).filter(UserLLMConfig.user_id == current_user.id).first()
            if user_config and user_config.api_key:
                api_key = user_config.api_key.strip()
                logger.info(f"[用户测试连接] 从用户配置读取API密钥，长度: {len(api_key)}")
            else:
                return LLMConfigTestResponse(
                    success=False,
                    message="API密钥不能为空，请在前端表单中输入API密钥或确保已保存配置",
                    provider=test_data.provider
                )
        
        # 根据provider选择默认配置
        provider = test_data.provider or "deepseek"
        
        if provider == "deepseek":
            base_url = (test_data.base_url or "https://api.deepseek.com/v1").strip()
            model_name = test_data.model_name or "deepseek-chat"
            # 确保base_url以/chat/completions结尾
            if not base_url.endswith("/chat/completions"):
                if not base_url.endswith("/"):
                    base_url += "/"
                base_url += "chat/completions"
        elif provider == "doubao":
            base_url = (test_data.base_url or "https://ark.cn-beijing.volces.com/api/v3/chat/completions").strip()
            model_name = test_data.model_name or "doubao-seed-1-6-lite-251015"
            # 豆包的base_url已经包含完整路径，不需要再添加/chat/completions
        elif provider == "qwen":
            base_url = (test_data.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
            model_name = test_data.model_name or "qwen3-next-80b-a3b-instruct"
            # 确保base_url以/chat/completions结尾
            if not base_url.endswith("/chat/completions"):
                if not base_url.endswith("/"):
                    base_url += "/"
                base_url += "chat/completions"
        else:
            return LLMConfigTestResponse(
                success=False,
                message=f"不支持的服务商: {provider}",
                provider=provider
            )
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"[用户测试连接] {provider} - API密钥长度: {len(api_key)}, 前缀: {api_key[:4]}..., Base URL: {base_url}, Model: {model_name}")
        
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
                logger.info(f"[用户测试连接] {provider} API密钥验证成功")
                return LLMConfigTestResponse(
                    success=True,
                    message="API密钥验证成功",
                    provider=provider
                )
            elif response.status_code == 401:
                # 尝试获取更详细的错误信息
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "API密钥无效或已过期")
                    logger.warning(f"[用户测试连接] {provider} API密钥验证失败: {error_msg}")
                except:
                    error_msg = "API密钥无效或已过期"
                    logger.warning(f"[用户测试连接] {provider} API密钥验证失败: 401 Unauthorized")
                
                return LLMConfigTestResponse(
                    success=False,
                    message=f"API密钥无效或已过期: {error_msg}",
                    provider=provider
                )
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except:
                    pass
                
                logger.warning(f"[用户测试连接] {provider} 连接测试失败: {error_msg}")
                return LLMConfigTestResponse(
                    success=False,
                    message=f"连接测试失败: {error_msg}",
                    provider=provider
                )
    except httpx.TimeoutException:
        logger.error(f"[用户测试连接] {test_data.provider} 连接超时")
        return LLMConfigTestResponse(
            success=False,
            message="连接超时，请检查网络连接或API服务是否可用",
            provider=test_data.provider or "deepseek"
        )
    except Exception as e:
        logger.error(f"[用户测试连接] 测试连接时发生错误: {e}", exc_info=True)
        return LLMConfigTestResponse(
            success=False,
            message=f"测试连接时发生错误: {str(e)}",
            provider=test_data.provider or "deepseek"
        )