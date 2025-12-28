from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from ....core.database import get_db
from ....models.resume import CandidateResume, ResumeTemplate
from ....models.user import User
from ....schemas.resume import ResumeCreate, ResumeResponse, ResumeListResponse
from ....api.v1.endpoints.users import get_current_user

router = APIRouter()

@router.post("/", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def create_resume(
    resume_data: ResumeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新简历（保存生成的规范化简历，不消耗使用次数）"""
    import logging
    logger = logging.getLogger(__name__)
    
    # 验证模板是否存在
    template = db.query(ResumeTemplate).filter(ResumeTemplate.id == resume_data.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 将 ResumeData 转换为字典（兼容 Pydantic v1 和 v2）
    try:
        resume_data_dict = resume_data.resume_data.model_dump() if hasattr(resume_data.resume_data, 'model_dump') else resume_data.resume_data.dict()
    except:
        resume_data_dict = resume_data.resume_data
    
    # 记录字段长度，用于调试
    title = (resume_data.title or "我的简历")[:255]  # 确保不超过255字符
    source_file_name = (resume_data.source_file_name or "")[:255] if resume_data.source_file_name else None
    source_file_type = (resume_data.source_file_type or "")[:100] if resume_data.source_file_type else None  # 确保不超过100字符
    source_file_path = (resume_data.source_file_path or "")[:500] if resume_data.source_file_path else None  # 确保不超过500字符
    
    logger.info(f"[保存简历] 字段长度检查 - title: {len(title)}, source_file_name: {len(source_file_name) if source_file_name else 0}, source_file_type: {len(source_file_type) if source_file_type else 0}, source_file_path: {len(source_file_path) if source_file_path else 0}")
    
    # 从解析数据中提取候选人姓名（如果前端没有提供，则从 resume_data 中提取）
    candidate_name = resume_data.candidate_name
    if not candidate_name and isinstance(resume_data_dict, dict) and 'basic_info' in resume_data_dict:
        candidate_name = resume_data_dict.get('basic_info', {}).get('name')
    
    # 获取 parsed_resume_id（如果提供）
    parsed_resume_id = getattr(resume_data, 'parsed_resume_id', None)
    
    db_resume = CandidateResume(
        user_id=current_user.id,
        template_id=resume_data.template_id,
        parsed_resume_id=parsed_resume_id,
        resume_data=resume_data_dict,
        candidate_name=candidate_name,
        title=title,
        source_file_name=source_file_name,
        source_file_type=source_file_type,
        source_file_path=source_file_path
    )
    db.add(db_resume)
    try:
        db.commit()
        db.refresh(db_resume)
    except Exception as e:
        db.rollback()
        logger.error(f"[保存简历] 数据库错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
    
    # 注意：使用次数在导出Word文档时消耗，保存简历时不消耗
    
    # 更新模板使用统计
    template.usage_count = (template.usage_count or 0) + 1
    
    db.commit()
    
    return db_resume

@router.post("/auto-save", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def auto_save_resume(
    resume_data: ResumeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """自动保存简历（不检查使用限制，不增加使用次数）"""
    import logging
    logger = logging.getLogger(__name__)
    
    # 验证模板是否存在
    template = db.query(ResumeTemplate).filter(ResumeTemplate.id == resume_data.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 将 ResumeData 转换为字典（兼容 Pydantic v1 和 v2）
    try:
        resume_data_dict = resume_data.resume_data.model_dump() if hasattr(resume_data.resume_data, 'model_dump') else resume_data.resume_data.dict()
    except:
        resume_data_dict = resume_data.resume_data
    
    # 记录字段长度，用于调试
    title = (resume_data.title or "我的简历")[:255]
    source_file_name = (resume_data.source_file_name or "")[:255] if resume_data.source_file_name else None
    source_file_type = (resume_data.source_file_type or "")[:100] if resume_data.source_file_type else None
    source_file_path = (resume_data.source_file_path or "")[:500] if resume_data.source_file_path else None
    
    logger.info(f"[自动保存简历] 字段长度检查 - title: {len(title)}, source_file_name: {len(source_file_name) if source_file_name else 0}")
    
    # 从解析数据中提取候选人姓名
    candidate_name = resume_data.candidate_name
    if not candidate_name and isinstance(resume_data_dict, dict) and 'basic_info' in resume_data_dict:
        candidate_name = resume_data_dict.get('basic_info', {}).get('name')
    
    # 获取 parsed_resume_id（如果提供）
    parsed_resume_id = getattr(resume_data, 'parsed_resume_id', None)
    
    db_resume = CandidateResume(
        user_id=current_user.id,
        template_id=resume_data.template_id,
        parsed_resume_id=parsed_resume_id,
        resume_data=resume_data_dict,
        candidate_name=candidate_name,
        title=title,
        source_file_name=source_file_name,
        source_file_type=source_file_type,
        source_file_path=source_file_path
    )
    db.add(db_resume)
    try:
        db.commit()
        db.refresh(db_resume)
    except Exception as e:
        db.rollback()
        logger.error(f"[自动保存简历] 数据库错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"自动保存失败: {str(e)}")
    
    # 注意：自动保存不增加使用次数，也不更新模板使用统计
    # 使用次数应该在智能匹配时已经增加
    
    logger.info(f"[自动保存简历] 成功保存，简历ID: {db_resume.id}")
    return db_resume

@router.get("/", response_model=List[ResumeListResponse])
async def get_resumes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索关键词（标题、文件名）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取简历列表（管理员可以看到所有数据，普通用户只能看到自己的）"""
    # 管理员可以看到所有数据，普通用户只能看到自己的
    if current_user.user_type == "super_admin":
        query = db.query(CandidateResume)
    else:
        query = db.query(CandidateResume).filter(CandidateResume.user_id == current_user.id)
    
    # 搜索功能
    if search:
        query = query.filter(
            (CandidateResume.title.contains(search)) |
            (CandidateResume.source_file_name.contains(search)) |
            (CandidateResume.candidate_name.contains(search))
        )
    
    # 按创建时间倒序（使用复合索引 idx_candidate_resume_user_created 优化）
    query = query.order_by(CandidateResume.created_at.desc())
    
    # 性能优化：先执行 count，再执行分页查询
    # 注意：count() 在大量数据时可能较慢，但为了分页信息必须执行
    total = query.count()
    
    # 使用 eager loading 优化关联查询，避免 N+1 问题
    from sqlalchemy.orm import joinedload
    resumes = query.options(
        joinedload(CandidateResume.template),
        joinedload(CandidateResume.parsed_resume)
    ).offset(skip).limit(limit).all()
    
    # 转换为响应格式，包含模板名称和解析结果名称
    result = []
    for resume in resumes:
        resume_dict = {
            "id": resume.id,
            "user_id": resume.user_id,
            "template_id": resume.template_id,
            "parsed_resume_id": resume.parsed_resume_id,
            "candidate_name": resume.candidate_name,
            "title": resume.title,
            "source_file_name": resume.source_file_name,
            "source_file_type": resume.source_file_type,
            "source_file_path": resume.source_file_path,
            "created_at": resume.created_at,
            "updated_at": resume.updated_at,
            "template_name": None,
            "parsed_resume_name": None
        }
        # 使用 eager loading 的结果，避免额外查询
        if resume.template:
            resume_dict["template_name"] = resume.template.name
        if resume.parsed_resume:
            resume_dict["parsed_resume_name"] = resume.parsed_resume.name
        result.append(resume_dict)
    
    return result

@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取简历详情（管理员可以查看所有数据，普通用户只能查看自己的）"""
    # 管理员可以查看所有数据，普通用户只能查看自己的
    if current_user.user_type == "super_admin":
        resume = db.query(CandidateResume).filter(CandidateResume.id == resume_id).first()
    else:
        resume = db.query(CandidateResume).filter(
            CandidateResume.id == resume_id,
            CandidateResume.user_id == current_user.id
        ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    return resume

@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除推荐报告（管理员可以删除所有数据，普通用户只能删除自己的数据）
    
    注意：删除推荐报告不会影响关联的解析结果和源文件
    """
    # 管理员可以删除所有数据，普通用户只能删除自己的数据
    if current_user.user_type == "super_admin":
        resume = db.query(CandidateResume).filter(CandidateResume.id == resume_id).first()
    else:
        resume = db.query(CandidateResume).filter(
            CandidateResume.id == resume_id,
            CandidateResume.user_id == current_user.id
        ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    # 记录关联信息（用于日志）
    parsed_resume_id = resume.parsed_resume_id
    
    try:
        db.delete(resume)
        db.commit()
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"用户 {current_user.id} 删除了推荐报告 {resume_id}，关联的解析结果ID: {parsed_resume_id}")
    except Exception as e:
        db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"删除推荐报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.put("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: int,
    resume_data: ResumeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新简历"""
    resume = db.query(CandidateResume).filter(
        CandidateResume.id == resume_id,
        CandidateResume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    # 更新字段
    resume.template_id = resume_data.template_id
    try:
        resume_data_dict = resume_data.resume_data.model_dump() if hasattr(resume_data.resume_data, 'model_dump') else resume_data.resume_data.dict()
    except:
        resume_data_dict = resume_data.resume_data
    resume.resume_data = resume_data_dict
    resume.title = resume_data.title or resume.title
    if resume_data.source_file_name is not None:
        resume.source_file_name = resume_data.source_file_name
    if resume_data.source_file_type is not None:
        resume.source_file_type = resume_data.source_file_type
    if resume_data.source_file_path is not None:
        resume.source_file_path = resume_data.source_file_path
    resume.updated_at = datetime.now()
    
    db.commit()
    db.refresh(resume)
    
    return resume

