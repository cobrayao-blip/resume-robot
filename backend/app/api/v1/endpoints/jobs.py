"""
岗位管理API端点
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional
from datetime import datetime
import logging

from ....core.database import get_db
from ....models.job import JobPosition, FilterRule, ResumeJobMatch, CompanyInfo, MatchModel
from ....models.resume import ParsedResume, CandidateResume
from ....models.user import User
from ....schemas.job import (
    JobPositionCreate, JobPositionUpdate, JobPositionResponse, JobPositionListResponse,
    JobPositionWithProfile, FilterRuleCreate, FilterRuleUpdate, FilterRuleResponse,
    ResumeJobMatchCreate, ResumeJobMatchResponse, ResumeJobMatchWithDetail, MatchListResponse,
    CompanyInfoCreate, CompanyInfoUpdate, CompanyInfoResponse,
    MatchModelCreate, MatchModelUpdate, MatchModelResponse
)
from ....api.v1.endpoints.users import get_current_user
from ....core.mongodb_service import mongodb_service
from ....core.tenant_dependency import require_tenant_id
from fastapi import Request

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== 岗位管理 ==========

@router.post("/positions", response_model=JobPositionResponse, status_code=status.HTTP_201_CREATED)
async def create_job_position(
    job_data: JobPositionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """创建岗位（自动关联tenant_id）"""
    try:
        # 如果提供了 department_id，需要验证部门是否存在且属于当前租户
        department_id = None
        if job_data.department_id:
            from ....models.organization import Department
            dept = db.query(Department).filter(
                Department.id == job_data.department_id,
                Department.tenant_id == tenant_id
            ).first()
            if not dept:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"部门ID {job_data.department_id} 不存在或不属于当前租户"
                )
            department_id = job_data.department_id
        
        db_job = JobPosition(
            title=job_data.title,
            department=job_data.department,  # 保留兼容字段
            department_id=department_id,  # 关联部门ID
            description=job_data.description,
            requirements=job_data.requirements,
            status=job_data.status or "draft",
            created_by=current_user.id,
            tenant_id=tenant_id
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        
        logger.info(f"岗位已创建: id={db_job.id}, title={db_job.title}, department_id={department_id}, user_id={current_user.id}, tenant_id={tenant_id}")
        return db_job
    except Exception as e:
        db.rollback()
        logger.error(f"创建岗位失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建岗位失败: {str(e)}")


@router.get("/positions", response_model=JobPositionListResponse)
async def get_job_positions(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="每页记录数"),
    status: Optional[str] = Query(None, description="岗位状态筛选: draft, published, closed"),
    search: Optional[str] = Query(None, description="搜索关键词（岗位名称、部门）"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """获取岗位列表（自动过滤tenant_id）"""
    try:
        query = db.query(JobPosition).filter(JobPosition.tenant_id == tenant_id)
        
        # 状态筛选
        if status:
            query = query.filter(JobPosition.status == status)
        
        # 搜索筛选
        if search:
            search_filter = or_(
                JobPosition.title.contains(search),
                JobPosition.department.contains(search)
            )
            query = query.filter(search_filter)
        
        # 总数
        total = query.count()
        
        # 分页查询
        jobs = query.order_by(JobPosition.created_at.desc()).offset(skip).limit(limit).all()
        
        return JobPositionListResponse(
            items=jobs,
            total=total,
            page=skip // limit + 1 if limit > 0 else 1,
            page_size=limit
        )
    except Exception as e:
        logger.error(f"获取岗位列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取岗位列表失败: {str(e)}")


@router.get("/positions/{job_id}", response_model=JobPositionWithProfile)
async def get_job_position(
    job_id: int,
    include_profile: bool = Query(False, description="是否包含岗位画像"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """获取岗位详情（自动过滤tenant_id）"""
    try:
        job = db.query(JobPosition).filter(
            JobPosition.id == job_id,
            JobPosition.tenant_id == tenant_id
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        
        response_data = JobPositionWithProfile.model_validate(job)
        
        # 如果需要包含岗位画像
        if include_profile and job.mongodb_id:
            profile = mongodb_service.get_job_profile(job_id)
            if profile:
                response_data.profile = profile.get("parsed_data")
        
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取岗位详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取岗位详情失败: {str(e)}")


@router.put("/positions/{job_id}", response_model=JobPositionResponse)
async def update_job_position(
    job_id: int,
    job_data: JobPositionUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """更新岗位（自动过滤tenant_id）"""
    try:
        job = db.query(JobPosition).filter(
            JobPosition.id == job_id,
            JobPosition.tenant_id == tenant_id
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        
        # 检查权限（只能修改自己创建的岗位，或管理员）
        if job.created_by != current_user.id and current_user.user_type != "super_admin":
            raise HTTPException(status_code=403, detail="无权修改此岗位")
        
        # 更新字段
        update_data = job_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(job, field, value)
        
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        
        logger.info(f"岗位已更新: id={job_id}, user_id={current_user.id}")
        return job
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新岗位失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新岗位失败: {str(e)}")


@router.delete("/positions/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_position(
    job_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """删除岗位（自动过滤tenant_id）"""
    try:
        job = db.query(JobPosition).filter(
            JobPosition.id == job_id,
            JobPosition.tenant_id == tenant_id
        ).first()
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        
        # 检查权限
        if job.created_by != current_user.id and current_user.user_type != "super_admin":
            raise HTTPException(status_code=403, detail="无权删除此岗位")
        
        # 删除关联的匹配记录（级联删除）
        db.query(ResumeJobMatch).filter(ResumeJobMatch.job_id == job_id).delete()
        
        # 删除岗位
        db.delete(job)
        db.commit()
        
        logger.info(f"岗位已删除: id={job_id}, user_id={current_user.id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除岗位失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除岗位失败: {str(e)}")


# ========== 筛选规则管理 ==========

@router.post("/filter-rules", response_model=FilterRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_filter_rule(
    rule_data: FilterRuleCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """创建筛选规则（自动关联tenant_id）"""
    try:
        db_rule = FilterRule(
            name=rule_data.name,
            description=rule_data.description,
            rule_type=rule_data.rule_type,
            rule_config=rule_data.rule_config,
            logic_operator=rule_data.logic_operator or "AND",
            priority=rule_data.priority or 0,
            is_active=rule_data.is_active if rule_data.is_active is not None else True,
            created_by=current_user.id,
            tenant_id=tenant_id
        )
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)
        
        logger.info(f"筛选规则已创建: id={db_rule.id}, name={db_rule.name}, user_id={current_user.id}")
        return db_rule
    except Exception as e:
        db.rollback()
        logger.error(f"创建筛选规则失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建筛选规则失败: {str(e)}")


@router.get("/filter-rules", response_model=List[FilterRuleResponse])
async def get_filter_rules(
    rule_type: Optional[str] = Query(None, description="规则类型筛选"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """获取筛选规则列表（自动过滤tenant_id）"""
    try:
        query = db.query(FilterRule).filter(FilterRule.tenant_id == tenant_id)
        
        if rule_type:
            query = query.filter(FilterRule.rule_type == rule_type)
        if is_active is not None:
            query = query.filter(FilterRule.is_active == is_active)
        
        rules = query.order_by(FilterRule.priority.desc(), FilterRule.created_at.desc()).all()
        return rules
    except Exception as e:
        logger.error(f"获取筛选规则列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取筛选规则列表失败: {str(e)}")


@router.get("/filter-rules/{rule_id}", response_model=FilterRuleResponse)
async def get_filter_rule(
    rule_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """获取筛选规则详情（自动过滤tenant_id）"""
    rule = db.query(FilterRule).filter(
        FilterRule.id == rule_id,
        FilterRule.tenant_id == tenant_id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="筛选规则不存在")
    return rule


@router.put("/filter-rules/{rule_id}", response_model=FilterRuleResponse)
async def update_filter_rule(
    rule_id: int,
    rule_data: FilterRuleUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """更新筛选规则（自动过滤tenant_id）"""
    try:
        rule = db.query(FilterRule).filter(
            FilterRule.id == rule_id,
            FilterRule.tenant_id == tenant_id
        ).first()
        if not rule:
            raise HTTPException(status_code=404, detail="筛选规则不存在")
        
        # 检查权限
        if rule.created_by != current_user.id and current_user.user_type != "super_admin":
            raise HTTPException(status_code=403, detail="无权修改此规则")
        
        update_data = rule_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rule, field, value)
        
        rule.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(rule)
        
        logger.info(f"筛选规则已更新: id={rule_id}, user_id={current_user.id}")
        return rule
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新筛选规则失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新筛选规则失败: {str(e)}")


@router.delete("/filter-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter_rule(
    rule_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """删除筛选规则（自动过滤tenant_id）"""
    try:
        rule = db.query(FilterRule).filter(
            FilterRule.id == rule_id,
            FilterRule.tenant_id == tenant_id
        ).first()
        if not rule:
            raise HTTPException(status_code=404, detail="筛选规则不存在")
        
        # 检查权限
        if rule.created_by != current_user.id and current_user.user_type != "super_admin":
            raise HTTPException(status_code=403, detail="无权删除此规则")
        
        db.delete(rule)
        db.commit()
        
        logger.info(f"筛选规则已删除: id={rule_id}, user_id={current_user.id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除筛选规则失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除筛选规则失败: {str(e)}")


# ========== 公司信息管理 ==========

@router.post("/company-info", response_model=CompanyInfoResponse, status_code=status.HTTP_201_CREATED)
async def create_company_info(
    company_data: CompanyInfoCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """创建或更新公司信息（每个租户只能有一条记录，自动关联tenant_id）"""
    try:
        # 检查是否已存在（按tenant_id查询）
        existing = db.query(CompanyInfo).filter(CompanyInfo.tenant_id == tenant_id).first()
        
        if existing:
            # 更新现有记录
            update_data = company_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(existing, field, value)
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            logger.info(f"公司信息已更新: id={existing.id}, tenant_id={tenant_id}, user_id={current_user.id}")
            return existing
        else:
            # 创建新记录
            db_company = CompanyInfo(**company_data.dict(), tenant_id=tenant_id)
            db.add(db_company)
            db.commit()
            db.refresh(db_company)
            logger.info(f"公司信息已创建: id={db_company.id}, tenant_id={tenant_id}, user_id={current_user.id}")
            return db_company
    except Exception as e:
        db.rollback()
        logger.error(f"创建/更新公司信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建/更新公司信息失败: {str(e)}")


@router.get("/company-info", response_model=CompanyInfoResponse)
async def get_company_info(
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """获取公司信息（自动过滤tenant_id）"""
    company = db.query(CompanyInfo).filter(CompanyInfo.tenant_id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="公司信息不存在")
    return company


@router.put("/company-info/{company_id}", response_model=CompanyInfoResponse)
async def update_company_info(
    company_id: int,
    company_data: CompanyInfoUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """更新公司信息（自动过滤tenant_id）"""
    try:
        company = db.query(CompanyInfo).filter(
            CompanyInfo.id == company_id,
            CompanyInfo.tenant_id == tenant_id
        ).first()
        if not company:
            raise HTTPException(status_code=404, detail="公司信息不存在")
        
        update_data = company_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)
        
        company.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(company)
        
        logger.info(f"公司信息已更新: id={company_id}, user_id={current_user.id}")
        return company
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新公司信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新公司信息失败: {str(e)}")


# ========== 匹配模型管理 ==========

@router.post("/match-models", response_model=MatchModelResponse, status_code=status.HTTP_201_CREATED)
async def create_match_model(
    model_data: MatchModelCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """创建匹配模型（自动关联tenant_id）"""
    try:
        # 如果设置为默认模型，取消同一租户的其他默认模型
        if model_data.is_default:
            db.query(MatchModel).filter(
                MatchModel.tenant_id == tenant_id,
                MatchModel.is_default == True
            ).update({"is_default": False})
        
        db_model = MatchModel(
            name=model_data.name,
            description=model_data.description,
            model_type=model_data.model_type,
            model_config=model_data.model_config,
            is_default=model_data.is_default or False,
            is_active=model_data.is_active if model_data.is_active is not None else True,
            created_by=current_user.id,
            tenant_id=tenant_id
        )
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        
        logger.info(f"匹配模型已创建: id={db_model.id}, name={db_model.name}, user_id={current_user.id}")
        return db_model
    except Exception as e:
        db.rollback()
        logger.error(f"创建匹配模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建匹配模型失败: {str(e)}")


@router.get("/match-models", response_model=List[MatchModelResponse])
async def get_match_models(
    model_type: Optional[str] = Query(None, description="模型类型筛选"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """获取匹配模型列表（自动过滤tenant_id）"""
    try:
        query = db.query(MatchModel).filter(MatchModel.tenant_id == tenant_id)
        
        if model_type:
            query = query.filter(MatchModel.model_type == model_type)
        if is_active is not None:
            query = query.filter(MatchModel.is_active == is_active)
        
        models = query.order_by(MatchModel.is_default.desc(), MatchModel.created_at.desc()).all()
        return models
    except Exception as e:
        logger.error(f"获取匹配模型列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取匹配模型列表失败: {str(e)}")


@router.get("/match-models/{model_id}", response_model=MatchModelResponse)
async def get_match_model(
    model_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """获取匹配模型详情（自动过滤tenant_id）"""
    model = db.query(MatchModel).filter(
        MatchModel.id == model_id,
        MatchModel.tenant_id == tenant_id
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail="匹配模型不存在")
    return model


@router.put("/match-models/{model_id}", response_model=MatchModelResponse)
async def update_match_model(
    model_id: int,
    model_data: MatchModelUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """更新匹配模型（自动过滤tenant_id）"""
    try:
        model = db.query(MatchModel).filter(
            MatchModel.id == model_id,
            MatchModel.tenant_id == tenant_id
        ).first()
        if not model:
            raise HTTPException(status_code=404, detail="匹配模型不存在")
        
        # 如果设置为默认模型，取消同一租户的其他默认模型
        if model_data.is_default:
            db.query(MatchModel).filter(
                and_(
                    MatchModel.tenant_id == tenant_id,
                    MatchModel.id != model_id,
                    MatchModel.is_default == True
                )
            ).update({"is_default": False})
        
        update_data = model_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(model, field, value)
        
        model.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(model)
        
        logger.info(f"匹配模型已更新: id={model_id}, user_id={current_user.id}")
        return model
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新匹配模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新匹配模型失败: {str(e)}")


@router.delete("/match-models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_match_model(
    model_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """删除匹配模型（自动过滤tenant_id）"""
    try:
        model = db.query(MatchModel).filter(
            MatchModel.id == model_id,
            MatchModel.tenant_id == tenant_id
        ).first()
        if not model:
            raise HTTPException(status_code=404, detail="匹配模型不存在")
        
        # 检查权限
        if model.created_by != current_user.id and current_user.user_type != "super_admin":
            raise HTTPException(status_code=403, detail="无权删除此模型")
        
        db.delete(model)
        db.commit()
        
        logger.info(f"匹配模型已删除: id={model_id}, user_id={current_user.id}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除匹配模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除匹配模型失败: {str(e)}")


# ========== 岗位画像解析 ==========

@router.post("/positions/{job_id}/parse-profile", status_code=status.HTTP_200_OK)
async def parse_job_profile(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """解析岗位画像（使用LLM）"""
    try:
        from ....services.job_service import JobService
        
        job_service = JobService(db_session=db)
        parsed_data = await job_service.parse_job_profile(job_id)
        
        logger.info(f"岗位画像解析完成: job_id={job_id}, user_id={current_user.id}")
        return {"success": True, "data": parsed_data, "message": "岗位画像解析成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"解析岗位画像失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"解析岗位画像失败: {str(e)}")


@router.post("/positions/{job_id}/vectorize", status_code=status.HTTP_200_OK)
async def vectorize_job(
    job_id: int,
    embedding_model: str = Query("deepseek", description="向量化模型: deepseek/qwen"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将岗位向量化并存储到Milvus"""
    try:
        from ....services.job_service import JobService
        
        job_service = JobService(db_session=db)
        vector_id = await job_service.vectorize_job(job_id, embedding_model)
        
        logger.info(f"岗位向量化完成: job_id={job_id}, vector_id={vector_id}, user_id={current_user.id}")
        return {"success": True, "data": {"vector_id": vector_id}, "message": "岗位向量化成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"岗位向量化失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"岗位向量化失败: {str(e)}")


@router.post("/positions/{job_id}/publish", response_model=JobPositionResponse)
async def publish_job(
    job_id: int,
    auto_parse: bool = Query(True, description="是否自动解析岗位画像"),
    auto_vectorize: bool = Query(True, description="是否自动向量化"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """发布岗位（自动解析画像和向量化）"""
    try:
        job = db.query(JobPosition).filter(JobPosition.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        
        # 检查权限
        if job.created_by != current_user.id and current_user.user_type != "super_admin":
            raise HTTPException(status_code=403, detail="无权发布此岗位")
        
        # 更新状态
        job.status = "published"
        
        # 自动解析画像
        if auto_parse and not job.mongodb_id:
            from ....services.job_service import JobService
            job_service = JobService(db_session=db)
            await job_service.parse_job_profile(job_id)
            db.refresh(job)
        
        # 自动向量化
        if auto_vectorize and job.mongodb_id and not job.vector_id:
            from ....services.job_service import JobService
            job_service = JobService(db_session=db)
            await job_service.vectorize_job(job_id)
            db.refresh(job)
        
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        
        logger.info(f"岗位已发布: id={job_id}, user_id={current_user.id}")
        return job
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"发布岗位失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发布岗位失败: {str(e)}")


# ========== 预筛选功能 ==========

@router.post("/filter/execute", status_code=status.HTTP_200_OK)
async def execute_filter(
    resume_id: int = Query(..., description="简历ID（parsed_resume_id或candidate_resume_id）"),
    resume_type: str = Query("parsed", description="简历类型: parsed/candidate"),
    rule_ids: Optional[List[int]] = Query(None, description="要执行的规则ID列表（为空则执行所有活跃规则）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """执行预筛选规则"""
    try:
        from ....services.filter_service import FilterService
        
        # 获取简历数据
        if resume_type == "parsed":
            parsed_resume = db.query(ParsedResume).filter(ParsedResume.id == resume_id).first()
            if not parsed_resume:
                raise HTTPException(status_code=404, detail="解析结果不存在")
            
            # 尝试从MongoDB获取
            resume_doc = mongodb_service.get_parsed_resume(resume_id)
            if resume_doc:
                resume_data = resume_doc.get("parsed_data", {})
            else:
                # 从PostgreSQL获取
                resume_data = parsed_resume.parsed_data
        else:
            candidate_resume = db.query(CandidateResume).filter(CandidateResume.id == resume_id).first()
            if not candidate_resume:
                raise HTTPException(status_code=404, detail="简历不存在")
            
            # 从resume_data获取
            resume_data = candidate_resume.resume_data
        
        # 执行筛选规则
        filter_service = FilterService(db_session=db)
        result = filter_service.execute_filter_rules(
            resume_data=resume_data,
            rule_ids=rule_ids,
            all_rules=rule_ids is None
        )
        
        logger.info(f"预筛选完成: resume_id={resume_id}, resume_type={resume_type}, passed={result['passed']}, user_id={current_user.id}")
        return {
            "success": True,
            "data": result,
            "message": "预筛选完成"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行预筛选失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行预筛选失败: {str(e)}")


@router.post("/filter/batch-execute", status_code=status.HTTP_200_OK)
async def batch_execute_filter(
    resume_ids: List[int] = Query(..., description="简历ID列表"),
    resume_type: str = Query("parsed", description="简历类型: parsed/candidate"),
    rule_ids: Optional[List[int]] = Query(None, description="要执行的规则ID列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量执行预筛选"""
    try:
        from ....services.filter_service import FilterService
        
        filter_service = FilterService(db_session=db)
        results = []
        
        for resume_id in resume_ids:
            try:
                # 获取简历数据
                if resume_type == "parsed":
                    parsed_resume = db.query(ParsedResume).filter(ParsedResume.id == resume_id).first()
                    if not parsed_resume:
                        results.append({
                            "resume_id": resume_id,
                            "success": False,
                            "error": "解析结果不存在"
                        })
                        continue
                    
                    resume_doc = mongodb_service.get_parsed_resume(resume_id)
                    if resume_doc:
                        resume_data = resume_doc.get("parsed_data", {})
                    else:
                        resume_data = parsed_resume.parsed_data
                else:
                    candidate_resume = db.query(CandidateResume).filter(CandidateResume.id == resume_id).first()
                    if not candidate_resume:
                        results.append({
                            "resume_id": resume_id,
                            "success": False,
                            "error": "简历不存在"
                        })
                        continue
                    
                    resume_data = candidate_resume.resume_data
                
                # 执行筛选
                result = filter_service.execute_filter_rules(
                    resume_data=resume_data,
                    rule_ids=rule_ids,
                    all_rules=rule_ids is None
                )
                
                results.append({
                    "resume_id": resume_id,
                    "success": True,
                    "data": result
                })
                
            except Exception as e:
                logger.error(f"批量预筛选单个简历失败: resume_id={resume_id}, error={e}")
                results.append({
                    "resume_id": resume_id,
                    "success": False,
                    "error": str(e)
                })
        
        # 统计结果
        total = len(results)
        success_count = sum(1 for r in results if r.get("success"))
        passed_count = sum(1 for r in results if r.get("success") and r.get("data", {}).get("passed"))
        
        logger.info(f"批量预筛选完成: total={total}, success={success_count}, passed={passed_count}, user_id={current_user.id}")
        return {
            "success": True,
            "data": {
                "results": results,
                "summary": {
                    "total": total,
                    "success": success_count,
                    "passed": passed_count,
                    "failed": total - passed_count
                }
            },
            "message": f"批量预筛选完成: 共{total}份简历，成功{success_count}份，通过{passed_count}份"
        }
        
    except Exception as e:
        logger.error(f"批量预筛选失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量预筛选失败: {str(e)}")


# ========== 简历匹配功能 ==========

@router.post("/match/resume-to-job", status_code=status.HTTP_200_OK)
async def match_resume_to_job(
    resume_id: int = Query(..., description="简历ID"),
    job_id: int = Query(..., description="岗位ID"),
    resume_type: str = Query("parsed", description="简历类型: parsed/candidate"),
    match_model_id: Optional[int] = Query(None, description="匹配模型ID（为空则使用默认模型）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """匹配简历与岗位"""
    try:
        from ....services.match_service import MatchService
        
        match_service = MatchService(db_session=db)
        result = await match_service.match_resume_to_job(
            resume_id=resume_id,
            job_id=job_id,
            resume_type=resume_type,
            match_model_id=match_model_id
        )
        
        logger.info(f"简历匹配完成: resume_id={resume_id}, job_id={job_id}, score={result['match_score']}, user_id={current_user.id}")
        return {
            "success": True,
            "data": result,
            "message": "简历匹配完成"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"简历匹配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"简历匹配失败: {str(e)}")


@router.post("/match/batch-match", status_code=status.HTTP_200_OK)
async def batch_match_resumes(
    resume_ids: List[int] = Query(..., description="简历ID列表"),
    job_id: int = Query(..., description="岗位ID"),
    resume_type: str = Query("parsed", description="简历类型: parsed/candidate"),
    match_model_id: Optional[int] = Query(None, description="匹配模型ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量匹配简历与岗位"""
    try:
        from ....services.match_service import MatchService
        
        match_service = MatchService(db_session=db)
        results = []
        
        for resume_id in resume_ids:
            try:
                result = await match_service.match_resume_to_job(
                    resume_id=resume_id,
                    job_id=job_id,
                    resume_type=resume_type,
                    match_model_id=match_model_id
                )
                results.append({
                    "resume_id": resume_id,
                    "success": True,
                    "data": result
                })
            except Exception as e:
                logger.error(f"批量匹配单个简历失败: resume_id={resume_id}, error={e}")
                results.append({
                    "resume_id": resume_id,
                    "success": False,
                    "error": str(e)
                })
        
        # 统计结果
        total = len(results)
        success_count = sum(1 for r in results if r.get("success"))
        strongly_recommended = sum(1 for r in results if r.get("success") and r.get("data", {}).get("match_label") == "强烈推荐")
        recommended = sum(1 for r in results if r.get("success") and r.get("data", {}).get("match_label") == "推荐")
        
        logger.info(f"批量匹配完成: total={total}, success={success_count}, strongly_recommended={strongly_recommended}, recommended={recommended}, user_id={current_user.id}")
        return {
            "success": True,
            "data": {
                "results": results,
                "summary": {
                    "total": total,
                    "success": success_count,
                    "strongly_recommended": strongly_recommended,
                    "recommended": recommended,
                    "cautious": sum(1 for r in results if r.get("success") and r.get("data", {}).get("match_label") == "谨慎推荐"),
                    "not_recommended": sum(1 for r in results if r.get("success") and r.get("data", {}).get("match_label") == "不推荐")
                }
            },
            "message": f"批量匹配完成: 共{total}份简历，成功{success_count}份"
        }
        
    except Exception as e:
        logger.error(f"批量匹配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量匹配失败: {str(e)}")


@router.get("/match/results", response_model=MatchListResponse)
async def get_match_results(
    job_id: Optional[int] = Query(None, description="岗位ID筛选"),
    resume_id: Optional[int] = Query(None, description="简历ID筛选"),
    match_label: Optional[str] = Query(None, description="匹配标签筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="每页记录数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取匹配结果列表"""
    try:
        query = db.query(ResumeJobMatch)
        
        if job_id:
            query = query.filter(ResumeJobMatch.job_id == job_id)
        if resume_id:
            query = query.filter(ResumeJobMatch.resume_id == resume_id)
        if match_label:
            query = query.filter(ResumeJobMatch.match_label == match_label)
        if status:
            query = query.filter(ResumeJobMatch.status == status)
        
        # 总数
        total = query.count()
        
        # 分页查询（按匹配分数降序）
        matches = query.order_by(ResumeJobMatch.match_score.desc()).offset(skip).limit(limit).all()
        
        return MatchListResponse(
            items=matches,
            total=total,
            page=skip // limit + 1 if limit > 0 else 1,
            page_size=limit
        )
        
    except Exception as e:
        logger.error(f"获取匹配结果列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取匹配结果列表失败: {str(e)}")


@router.get("/match/results/{match_id}", response_model=ResumeJobMatchWithDetail)
async def get_match_result_detail(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取匹配结果详情（包含匹配详情）"""
    try:
        match = db.query(ResumeJobMatch).filter(ResumeJobMatch.id == match_id).first()
        if not match:
            raise HTTPException(status_code=404, detail="匹配记录不存在")
        
        response_data = ResumeJobMatchWithDetail.model_validate(match)
        
        # 获取匹配详情（从MongoDB）
        if match.mongodb_detail_id:
            match_detail = mongodb_service.get_match_detail(match_id)
            if match_detail:
                response_data.match_detail = match_detail
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取匹配结果详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取匹配结果详情失败: {str(e)}")


@router.put("/match/results/{match_id}/status", response_model=ResumeJobMatchResponse)
async def update_match_status(
    match_id: int,
    new_status: str = Query(..., description="新状态: pending/reviewed/rejected/accepted"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新匹配状态"""
    try:
        match = db.query(ResumeJobMatch).filter(ResumeJobMatch.id == match_id).first()
        if not match:
            raise HTTPException(status_code=404, detail="匹配记录不存在")
        
        if new_status not in ["pending", "reviewed", "rejected", "accepted"]:
            raise HTTPException(status_code=400, detail="无效的状态值")
        
        match.status = new_status
        match.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(match)
        
        logger.info(f"匹配状态已更新: match_id={match_id}, status={new_status}, user_id={current_user.id}")
        return match
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新匹配状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新匹配状态失败: {str(e)}")

