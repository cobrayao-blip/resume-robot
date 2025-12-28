from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
from ....core.database import get_db
from ....core.tenant_dependency import get_tenant_id
from ....models.resume import ParsedResume, CandidateResume
from ....models.user import User
from ....schemas.resume import ParsedResumeCreate, ParsedResumeResponse, ParsedResumeListResponse
from ....api.v1.endpoints.users import get_current_user
from fastapi import Request
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=ParsedResumeResponse, status_code=status.HTTP_201_CREATED)
async def create_parsed_resume(
    parsed_resume_data: ParsedResumeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: Optional[int] = Depends(get_tenant_id)
):
    """保存简历解析结果"""
    # 从解析数据中提取候选人姓名（如果前端没有提供，则从 parsed_data 中提取）
    candidate_name = parsed_resume_data.candidate_name
    if not candidate_name and isinstance(parsed_resume_data.parsed_data, dict) and 'basic_info' in parsed_resume_data.parsed_data:
        candidate_name = parsed_resume_data.parsed_data.get('basic_info', {}).get('name')
    
    db_parsed_resume = ParsedResume(
        tenant_id=tenant_id,
        user_id=current_user.id,
        name=parsed_resume_data.name,
        parsed_data=parsed_resume_data.parsed_data,
        raw_text=parsed_resume_data.raw_text,
        candidate_name=candidate_name,
        source_file_name=parsed_resume_data.source_file_name,
        source_file_type=parsed_resume_data.source_file_type,
        source_file_path=getattr(parsed_resume_data, 'source_file_path', None),
        file_hash=parsed_resume_data.file_hash,
        validation=parsed_resume_data.validation,
        correction=parsed_resume_data.correction,
        quality_analysis=parsed_resume_data.quality_analysis
    )
    
    db.add(db_parsed_resume)
    db.commit()
    db.refresh(db_parsed_resume)
    
    return db_parsed_resume

@router.get("/", response_model=List[ParsedResumeListResponse])
async def get_parsed_resumes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索关键词（名称、文件名、候选人姓名）"),
    status: Optional[str] = Query(None, description="简历状态：filtered（已过滤）"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: Optional[int] = Depends(get_tenant_id)
):
    """
    获取解析结果列表（简历总库）
    
    - 按tenant_id自动过滤
    - 支持搜索和状态筛选
    - 支持分页
    """
    # 按tenant_id过滤（多租户隔离）
    query = db.query(ParsedResume).filter(ParsedResume.tenant_id == tenant_id)
    
    # 搜索功能
    if search:
        query = query.filter(
            (ParsedResume.name.contains(search)) |
            (ParsedResume.source_file_name.contains(search)) |
            (ParsedResume.candidate_name.contains(search))
        )
    
    # 状态筛选（用于过滤箱）
    if status == "filtered":
        # 查询被过滤的简历（需要检查是否有filter_result）
        # 这里暂时通过检查是否有匹配记录来判断，后续可以通过添加字段优化
        from ....models.job import ResumeJobMatch
        filtered_resume_ids = db.query(ResumeJobMatch.resume_id).filter(
            ResumeJobMatch.tenant_id == tenant_id,
            ResumeJobMatch.status == "rejected"
        ).subquery()
        query = query.filter(ParsedResume.id.in_(filtered_resume_ids))
    
    # 按创建时间倒序（使用复合索引 idx_parsed_user_created 优化）
    query = query.order_by(ParsedResume.created_at.desc())
    
    # 性能优化：先执行count，再执行分页查询
    total = query.count()
    resumes = query.offset(skip).limit(limit).all()
    
    # 返回包含total的响应（使用字典包装，前端可以解析）
    # 注意：FastAPI的List响应模型不支持额外字段，所以这里返回列表
    # 前端可以通过响应头或单独的count端点获取total
    # 暂时返回列表，前端使用列表长度作为total（不准确但可用）
    return resumes

@router.get("/{parsed_resume_id}", response_model=ParsedResumeResponse)
async def get_parsed_resume(
    parsed_resume_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: Optional[int] = Depends(get_tenant_id)
):
    """获取解析结果详情（按tenant_id过滤）"""
    parsed_resume = db.query(ParsedResume).filter(
        ParsedResume.id == parsed_resume_id,
        ParsedResume.tenant_id == tenant_id
    ).first()
    
    if not parsed_resume:
        raise HTTPException(status_code=404, detail="解析结果不存在")
    
    return parsed_resume

@router.delete("/{parsed_resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parsed_resume(
    parsed_resume_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: Optional[int] = Depends(get_tenant_id)
):
    """
    删除解析结果（按tenant_id过滤）
    
    注意：解析结果一旦生成后就是独立的，删除解析结果不会影响已生成的推荐报告。
    推荐报告中的数据已经完整保存，不依赖解析结果。
    """
    # 按tenant_id过滤
    parsed_resume = db.query(ParsedResume).filter(
        ParsedResume.id == parsed_resume_id,
        ParsedResume.tenant_id == tenant_id
    ).first()
    
    if not parsed_resume:
        raise HTTPException(status_code=404, detail="解析结果不存在")
    
    # 记录关联信息（仅用于日志，不影响删除）
    related_candidate_resumes = db.query(CandidateResume).filter(
        CandidateResume.parsed_resume_id == parsed_resume_id,
        CandidateResume.user_id == current_user.id
    ).count()
    
    # 直接删除，不检查依赖（推荐报告已独立，不依赖解析结果）
    # 但需要先解除外键关联，避免数据库约束错误
    try:
        # 先将关联的推荐报告的 parsed_resume_id 设置为 None（解除关联）
        db.query(CandidateResume).filter(
            CandidateResume.parsed_resume_id == parsed_resume_id,
            CandidateResume.user_id == current_user.id
        ).update({CandidateResume.parsed_resume_id: None})
        
        # 然后删除解析结果
        db.delete(parsed_resume)
        db.commit()
        logger.info(f"用户 {current_user.id} 删除了解析结果 {parsed_resume_id}，关联的推荐报告数量：{related_candidate_resumes}（已独立，不受影响）")
    except Exception as e:
        db.rollback()
        logger.error(f"删除解析结果失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)
