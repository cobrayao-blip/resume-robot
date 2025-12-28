from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Query, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import tempfile
import os
import logging
from ....core.database import get_db
from ....core.config import settings
from ....core.constants import ALLOWED_FILE_TYPES, MAX_FILE_SIZE_MB
from ....models.user import User
from ....api.v1.endpoints.users import get_current_user
from ....services.resume_parser import resume_parser
from ....services.deepseek_service import DeepSeekService, DeepSeekError, DeepSeekAuthError, deepseek_service
from ....services.llm_service import llm_service
from ....services.cache_service import cache_service
from ....services.data_validator import data_validator
# content_optimizer 和 conversation_service 已删除（简历内容优化功能，非模板设计功能）
# 如需恢复，请重新创建这两个服务文件
# from ....services.content_optimizer import ContentOptimizer, content_optimizer
# from ....services.conversation_service import conversation_service
from ....services.file_storage import file_storage_service
from ....schemas.resume import ResumeData, MatchFieldsRequest
from ....utils.file_validator import validate_file_type

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

@router.post("/parse-resume")
async def parse_resume(
    file: UploadFile = File(..., description="简历文件（PDF或Word格式，最大10MB）"),
    force_refresh: bool = Query(False, description="强制重新解析，跳过缓存。默认False，如果文件已解析过会返回缓存结果"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    解析上传的简历文件
    
    使用AI大模型（DeepSeek或豆包）解析简历文件，提取结构化信息。
    
    **功能说明**:
    - 支持PDF和Word格式（.pdf, .docx, .doc）
    - 自动检测文件类型（通过文件头验证，防止伪造）
    - 文件去重：相同文件（MD5相同）会返回缓存结果
    - 使用次数限制：普通用户有月度使用限制
    
    **请求参数**:
    - `file`: 简历文件（multipart/form-data）
    - `force_refresh`: 是否强制重新解析（跳过缓存）
    
    **响应示例**:
    ```json
    {
      "success": true,
      "data": {
        "id": 123,
        "name": "张三详细解析结果",
        "parsed_data": {
          "basic_info": {
            "name": "张三",
            "phone": "13800138000",
            "email": "zhangsan@example.com"
          },
          "work_experiences": [...],
          "education": [...]
        },
        "file_hash": "abc123..."
      },
      "file_hash": "abc123..."
    }
    ```
    
    **错误响应**:
    - `400`: 文件类型不支持或文件过大
    - `403`: 使用次数已达上限
    - `502`: AI服务配置错误或API调用失败
    - `504`: 解析超时
    
    **注意事项**:
    - 如果用户已达到使用上限，将阻止解析
    - 管理员和模板设计师不受使用次数限制
    - 解析结果会异步进行质量分析和增强处理
    """
    # 检查使用次数限制（如果达到上限，阻止解析）
    from ....core.usage_limit import check_usage_limit
    # 管理员和模板设计师不受限制
    if current_user.user_type not in ["super_admin", "template_designer"]:
        # 检查使用次数重置日期
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        if current_user.usage_reset_date and current_user.usage_reset_date < now:
            # 重置使用次数
            current_user.current_month_usage = 0
            current_user.usage_reset_date = now + timedelta(days=30)
            db.commit()
        
        # 如果没有设置重置日期，设置一个
        if not current_user.usage_reset_date:
            current_user.usage_reset_date = now + timedelta(days=30)
            db.commit()
        
        # 检查是否超过限制
        if current_user.monthly_usage_limit is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="使用次数限制未设置，请联系管理员"
            )
        
        limit = current_user.monthly_usage_limit
        if current_user.current_month_usage >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="USAGE_LIMIT_EXCEEDED:你的使用次数超过上线，请联系管理员！"
            )
    # 验证文件类型（检查Content-Type）
    if not file.content_type or file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(400, "只支持PDF和Word文档")
    
    # 读取文件内容
    content = await file.read()
    
    # 校验文件大小
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"文件过大，最大支持{MAX_FILE_SIZE_MB}MB")
    
    # 验证文件内容（通过文件头检查真实类型，防止伪造）
    is_valid, error_msg = validate_file_type(file.content_type, content, file.filename)
    if not is_valid:
        logger.warning(f"文件验证失败: {file.filename} - {error_msg}")
        raise HTTPException(400, error_msg or "文件类型验证失败，可能不是有效的PDF或Word文档")

    # 计算文件hash（统一使用hash作为缓存key）
    import hashlib
    file_hash = hashlib.md5(content).hexdigest()

    # 检查是否已存在相同的解析结果和源文件（通过 file_hash）
    from ....models.resume import ParsedResume, SourceFile
    existing_parsed_resume = db.query(ParsedResume).filter(
        ParsedResume.file_hash == file_hash,
        ParsedResume.user_id == current_user.id
    ).order_by(ParsedResume.created_at.desc()).first()
    
    existing_source_file = db.query(SourceFile).filter(
        SourceFile.file_hash == file_hash,
        SourceFile.user_id == current_user.id
    ).first()

    # 检查缓存（除非强制刷新）
    if not force_refresh:
        cached_result = await cache_service.get_cached_result_by_hash(file_hash)
        if cached_result:
            logger.info(f"使用缓存结果，跳过AI解析: {file_hash[:8]}...")
            return {
                "success": True,
                "data": cached_result.get("data"),
                "validation": cached_result.get("validation"),
                "cached": True,  # 标记为缓存结果
                "file_hash": file_hash,  # 返回file_hash
                "existing_parsed_resume_id": existing_parsed_resume.id if existing_parsed_resume else None,  # 返回已存在的解析结果ID
                "source_file_id": existing_source_file.id if existing_source_file else None  # 返回源文件ID
            }
    else:
        logger.info(f"强制重新解析，跳过缓存检查: {file_hash[:8]}...")
        # 如果强制刷新，先删除旧缓存
        await cache_service.delete_cache_by_hash(file_hash)

    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # 解析简历
        ext = os.path.splitext(file.filename or '')[1].lower()
        if file.content_type == 'application/pdf' or ext == '.pdf':
            file_type = 'pdf'
        elif file.content_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'] or ext == '.docx':
            file_type = 'docx'
        elif file.content_type in ['application/msword'] or ext == '.doc':
            # 明确提示暂不支持 .doc 旧格式
            raise HTTPException(415, "暂不支持 .doc（旧版Word）文件，请将文件另存为 .docx 或导出为 PDF 再上传")
        else:
            raise HTTPException(400, "不支持的文件类型")
        # 设置用户上下文，用于选择使用平台Key还是用户Key
        llm_service.set_user_context(current_user, db)
        # 解析简历（核心步骤，必须完成）
        parsed_data = await resume_parser.parse_resume_file(
            tmp_path, 
            file_type,
            current_user,
            db
        )
        
        # 快速验证数据（本地验证，不调用AI）
        validation = await resume_parser.validate_parsed_data(parsed_data)
        
        # 保存源文件到文件存储服务和数据库
        saved_file_path = None
        source_file_id = None
        try:
            saved_file_path = file_storage_service.save_file(
                content, 
                file.filename or f"resume.{file_type}",
                current_user.id
            )
            logger.info(f"源文件已保存: {saved_file_path}")
            
            # 检查是否已存在相同的源文件（通过 file_hash）
            from ....models.resume import SourceFile
            existing_file = db.query(SourceFile).filter(
                SourceFile.file_hash == file_hash,
                SourceFile.user_id == current_user.id
            ).first()
            
            if not existing_file:
                # 创建新的 SourceFile 记录
                source_file = SourceFile(
                    user_id=current_user.id,
                    file_name=file.filename or f"resume.{file_type}",
                    file_type=file.content_type or file_type,
                    file_path=saved_file_path,
                    file_size=len(content),
                    file_hash=file_hash
                )
                db.add(source_file)
                db.commit()
                db.refresh(source_file)
                source_file_id = source_file.id
                logger.info(f"源文件已保存到数据库: {source_file_id}")
            else:
                source_file_id = existing_file.id
                logger.info(f"源文件已存在，使用现有记录: {source_file_id}")
        except Exception as e:
            logger.error(f"保存源文件失败: {e}", exc_info=True)
            # 文件保存失败不影响解析结果返回，只记录错误
        
        # 检查是否已存在相同的解析结果（通过 file_hash）
        from ....models.resume import ParsedResume
        existing_parsed_resume = db.query(ParsedResume).filter(
            ParsedResume.file_hash == file_hash,
            ParsedResume.user_id == current_user.id
        ).order_by(ParsedResume.created_at.desc()).first()
        
        # 立即返回基础解析结果，不等待增强功能
        # 增强功能（数据纠错、质量分析）将在后台异步处理或由前端按需调用
        response_data = {
            "success": True,
            "data": parsed_data,
            "validation": validation,
            "cached": False,
            "enhancements_pending": True,  # 标记增强功能待处理
            "source_file_name": file.filename,
            "source_file_type": file_type,
            "source_file_path": saved_file_path,  # 返回保存的文件路径
            "source_file_id": source_file_id,  # 返回源文件ID
            "existing_parsed_resume_id": existing_parsed_resume.id if existing_parsed_resume else None,  # 返回已存在的解析结果ID
            "file_hash": file_hash  # 返回文件hash
        }
        
        # 保存基础结果到缓存（立即保存，不等待增强功能）
        # 注意：file_hash已在前面计算，这里直接使用
        cache_result = {
            "data": parsed_data,
            "validation": validation
        }
        await cache_service.set_cached_result_by_hash(file_hash, cache_result)
        
        # 后台异步处理增强功能（不阻塞响应）
        import asyncio
        async def process_enhancements():
            try:
                # 数据验证和纠错
                correction_result = None
                try:
                    correction_result = await data_validator.validate_and_correct(parsed_data)
                    if correction_result and correction_result.get('corrected_data'):
                        # 更新缓存中的纠错数据
                        cache_result['correction'] = correction_result
                        await cache_service.set_cached_result_by_hash(file_hash, cache_result)
                        logger.info(f"数据纠错完成（后台），纠正了{len(correction_result.get('corrections', []))}个问题")
                except Exception as e:
                    logger.warning(f"数据验证和纠错失败（后台）: {e}")
                
                # ========================================
                # 简历质量分析（暂时关闭）
                # ========================================
                # 关闭原因：
                # 1. 当前质量分析是"写简历视角"（告诉候选人如何改简历），与猎头版"推荐报告"定位不一致
                # 2. 存在JSON解析错误（"无法解析API响应"），可能因输出格式不稳定或响应截断
                # 3. 错误日志可能干扰排查，且不影响核心功能（解析和导出）
                # 
                # 未来规划：
                # - 为"候选人版"单独设计质量分析功能（帮助候选人优化简历）
                # - 为"猎头版"设计"候选人评估报告"（匹配度、风险点、亮点提炼）
                # 
                # 恢复方法：
                # 取消下面的注释，恢复质量分析功能
                # ========================================
                # try:
                #     quality_analysis = await deepseek_service.analyze_resume_quality(parsed_data, None)
                #     cache_result['quality_analysis'] = quality_analysis
                #     await cache_service.set_cached_result_by_hash(file_hash, cache_result)
                #     logger.info("简历质量分析完成（后台）")
                # except Exception as e:
                #     logger.warning(f"简历质量分析失败（后台）: {e}")
            except Exception as e:
                logger.error(f"后台增强处理失败: {e}")
        
        # 启动后台任务（不等待完成）
        asyncio.create_task(process_enhancements())
        
        # 在响应中包含file_hash，方便前端后续获取增强结果
        response_data['file_hash'] = file_hash
        
        return response_data
        
    except DeepSeekError as e:
        error_detail = str(e)
        if "timeout" in error_detail.lower() or "超时" in error_detail:
            raise HTTPException(504, f"解析超时，请稍后重试或检查网络连接: {error_detail}")
        elif "network" in error_detail.lower() or "网络" in error_detail:
            raise HTTPException(503, f"网络连接失败，请检查网络后重试: {error_detail}")
        elif "rate limit" in error_detail.lower() or "限流" in error_detail:
            raise HTTPException(429, f"请求过于频繁，请稍后重试: {error_detail}")
        elif isinstance(e, DeepSeekAuthError) or "鉴权" in error_detail or "auth" in error_detail.lower():
            # DeepSeek API密钥问题，返回502而不是401，避免前端误判为用户认证失败
            raise HTTPException(502, f"AI服务配置错误: {error_detail}。请联系管理员检查API密钥配置。")
        else:
            # 其他错误使用原始状态码，但如果是401也改为502
            status_code = e.status_code if e.status_code != 401 else 502
            raise HTTPException(status_code, f"简历解析失败: {error_detail}")
    except Exception as e:
        import traceback
        error_detail = str(e)
        logger.error(f"简历解析异常: {error_detail}\n{traceback.format_exc()}")
        raise HTTPException(500, f"简历解析失败: {error_detail}")
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.post("/analyze-resume")
async def analyze_resume(
    resume_data: ResumeData,
    target_position: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    分析简历质量
    """
    try:
        # 设置用户上下文
        llm_service.set_user_context(current_user, db)
        # 使用全局服务实例（已设置用户上下文）
        analysis_result = await llm_service.analyze_resume_quality(
            resume_data.dict(),
            target_position
        )
        
        return {
            "success": True,
            "analysis": analysis_result
        }
        
    except DeepSeekError as e:
        raise HTTPException(e.status_code, f"简历分析失败: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"简历分析失败: {str(e)}")

# ========== 简历内容优化功能（已移除） ==========
# 以下API端点依赖 content_optimizer 和 conversation_service，这两个服务已删除
# 如需恢复，请重新创建这两个服务文件

@router.post("/generate-content")
async def generate_content(
    field_type: str = Body(...),
    resume_data: Dict[str, Any] = Body(...),
    context: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db)
):
    """
    生成缺失的内容（功能已禁用）
    field_type: 'professional_summary', 'work_achievements', 'project_outcome' 等
    """
    raise HTTPException(503, "内容生成功能已暂时禁用，相关服务已移除")

@router.post("/optimize-content")
async def optimize_content(
    original_content: str = Body(...),
    content_type: str = Body(...),
    target_position: Optional[str] = Body(None),
    db: Session = Depends(get_db)
):
    """
    优化现有内容（功能已禁用）
    content_type: 'work_responsibility', 'work_achievement', 'project_description' 等
    """
    raise HTTPException(503, "内容优化功能已暂时禁用，相关服务已移除")

@router.post("/conversation/start")
async def start_conversation(
    resume_data: Dict[str, Any] = Body(...),
    context: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db)
):
    """
    开始新的对话（功能已禁用）
    """
    raise HTTPException(503, "对话功能已暂时禁用，相关服务已移除")

@router.post("/conversation/chat")
async def chat(
    conversation_id: str = Body(...),
    message: str = Body(...),
    resume_data: Optional[Dict[str, Any]] = Body(None),
    db: Session = Depends(get_db)
):
    """
    进行对话（功能已禁用）
    """
    raise HTTPException(503, "对话功能已暂时禁用，相关服务已移除")

@router.get("/conversation/{conversation_id}/history")
async def get_conversation_history(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    获取对话历史（功能已禁用）
    """
    raise HTTPException(503, "对话功能已暂时禁用，相关服务已移除")

@router.post("/conversation/{conversation_id}/end")
async def end_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    结束对话（功能已禁用）
    """
    raise HTTPException(503, "对话功能已暂时禁用，相关服务已移除")

@router.get("/parse-resume/enhancements")
async def get_parse_enhancements(
    file_hash: str = Query(..., description="文件内容的哈希值"),
    db: Session = Depends(get_db)
):
    """
    获取简历解析的增强结果（数据纠错、质量分析等）
    前端可以在解析完成后轮询此接口获取增强结果
    """
    try:
        # 从缓存中获取增强结果
        # 注意：这里需要根据file_hash获取，实际实现中可能需要调整缓存key
        cached_result = await cache_service.get_cached_result_by_hash(file_hash)
        
        if not cached_result:
            return {
                "success": False,
                "message": "未找到解析结果或增强功能尚未完成"
            }
        
        return {
            "success": True,
            "correction": cached_result.get("correction"),
            "quality_analysis": cached_result.get("quality_analysis"),
            "enhancements_ready": bool(cached_result.get("quality_analysis") or cached_result.get("correction"))
        }
    except Exception as e:
        logger.error(f"获取增强结果失败: {e}")
        raise HTTPException(500, f"获取增强结果失败: {str(e)}")

@router.post("/match-fields")
async def match_template_fields(
    request: MatchFieldsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    智能匹配模板字段
    支持两种方式：
    1. 旧方式：只传 template_fields（字段列表）
    2. 新方式：传 template_structure（完整模板结构）+ parsed_data，让 DeepSeek 直接生成规范化简历
    """
    import time
    start_time = time.time()
    
    # 从请求中提取参数
    parsed_data = request.parsed_data
    template_fields = request.template_fields
    template_structure = request.template_structure
    
    # 如果提供了完整模板结构，使用新方式
    if template_structure:
        logger.info(f"[匹配开始] 使用新方式：根据模板结构生成规范化简历")
        # 检查模板是否有映射规则
        field_mapping = template_structure.get("field_mapping", {})
        # 检查映射规则的有效性：field_mapping应该是一个包含"field_mapping"键的字典
        has_mapping = False
        if field_mapping and isinstance(field_mapping, dict):
            inner_mapping = field_mapping.get("field_mapping", {})
            if inner_mapping and isinstance(inner_mapping, dict) and len(inner_mapping) > 0:
                has_mapping = True
        logger.info(f"[匹配开始] 模板名称: {template_structure.get('name', '未知')}, 组件数: {len(template_structure.get('components', []))}, 是否有映射规则: {has_mapping}")
        if has_mapping:
            logger.info(f"[匹配开始] 映射规则组件类型: {list(field_mapping.get('field_mapping', {}).keys())}")
        try:
            # 设置用户上下文
            llm_service.set_user_context(current_user, db)
            filled_template = await llm_service.fill_template_with_resume_data(
                template_structure,
                parsed_data
            )
            elapsed = time.time() - start_time
            logger.info(f"[匹配完成] 耗时: {elapsed:.2f}秒")
            return {
                "success": True,
                "filled_template": filled_template  # 返回填充后的完整模板
            }
        except Exception as e:
            logger.error(f"[匹配失败] {e}", exc_info=True)
            raise HTTPException(500, f"匹配失败: {str(e)}")
    
    # 旧方式：只匹配字段
    logger.info(f"[匹配开始] 使用旧方式：字段匹配，字段数: {len(template_fields) if template_fields else 0}")
    
    try:
        # 设置用户上下文
        llm_service.set_user_context(current_user, db)
        logger.info(f"[匹配进行] 调用llm_service.match_template_fields...")
        match_result = await llm_service.match_template_fields(
            parsed_data,
            template_fields or []
        )
        
        elapsed = time.time() - start_time
        matches_count = len(match_result.get('matches', {}))
        logger.info(f"[匹配完成] 耗时: {elapsed:.2f}秒, 匹配字段数: {matches_count}")
        
        return {
            "success": True,
            "matches": match_result.get("matches", {})
        }
        
    except DeepSeekError as e:
        error_detail = str(e)
        if "timeout" in error_detail.lower() or "超时" in error_detail:
            raise HTTPException(504, f"匹配超时，请稍后重试或检查网络连接: {error_detail}")
        elif "network" in error_detail.lower() or "网络" in error_detail:
            raise HTTPException(503, f"网络连接失败，请检查网络后重试: {error_detail}")
        elif "rate limit" in error_detail.lower() or "限流" in error_detail:
            raise HTTPException(429, f"请求过于频繁，请稍后重试: {error_detail}")
        elif isinstance(e, DeepSeekAuthError) or "鉴权" in error_detail or "auth" in error_detail.lower():
            # DeepSeek API密钥问题，返回502而不是401，避免前端误判为用户认证失败
            raise HTTPException(502, f"AI服务配置错误: {error_detail}。请联系管理员检查API密钥配置。")
        else:
            # 其他错误使用原始状态码，但如果是401也改为502
            status_code = e.status_code if e.status_code != 401 else 502
            raise HTTPException(status_code, f"字段匹配失败: {error_detail}")
    except Exception as e:
        import traceback
        error_detail = str(e)
        logger.error(f"字段匹配异常: {error_detail}\n{traceback.format_exc()}")
        raise HTTPException(500, f"字段匹配失败: {error_detail}")