"""
推荐报告模板管理API
用于设计和管理推荐报告的Word模板
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
import logging
from ....core.database import get_db
from ....models.resume import ResumeTemplate, TemplateVersion
from ....models.user import User
from ....schemas.resume import TemplateCreate, TemplateResponse
from ....api.v1.endpoints.users import get_current_user, get_current_user_optional
from ....services.llm_service import llm_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建推荐报告模板
    
    创建推荐报告模板，系统会自动分析模板结构并生成字段映射规则。
    
    **权限要求**: 所有登录用户
    
    **功能说明**:
    - 验证模板结构格式
    - 使用AI分析模板结构，生成字段映射规则（超时30秒）
    - 如果AI分析失败或超时，模板仍会创建但不包含映射规则
    - 创建模板版本记录
    
    **请求参数**:
    ```json
    {
      "name": "标准推荐报告模板",
      "description": "适用于技术岗位的推荐报告模板",
      "template_schema": {
        "components": [
          {
            "type": "basic_info",
            "fields": [...]
          }
        ]
      },
      "style_config": {
        "font": "Arial",
        "fontSize": 12
      }
    }
    ```
    """
    try:
        # 验证模板结构
        if not template_data.template_schema:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="template_schema 不能为空"
            )
        
        # 创建模板记录
        db_template = ResumeTemplate(
            name=template_data.name,
            description=template_data.description,
            template_schema=template_data.template_schema,
            style_config=template_data.style_config or {},
            is_public=template_data.is_public,
            created_by=current_user.id,
            version="1.0.0"
        )
        db.add(db_template)
        db.flush()  # 获取ID
        
        # 使用AI分析模板结构，生成字段映射规则
        field_mapping = None
        try:
            # 设置用户上下文
            llm_service.set_user_context(current_user, db)
            
            # 分析模板结构（超时30秒）
            field_mapping = await llm_service.analyze_template_structure(
                template_data.template_schema
            )
            
            # 将字段映射添加到template_schema中
            if field_mapping and isinstance(db_template.template_schema, dict):
                db_template.template_schema['field_mapping'] = field_mapping
                logger.info(f"模板 {db_template.id} 字段映射已生成")
        except Exception as e:
            logger.warning(f"模板 {db_template.id} AI分析失败: {e}，模板仍会创建但不包含字段映射")
        
        # 创建初始版本记录
        version = TemplateVersion(
            template_id=db_template.id,
            version=db_template.version,
            version_name="初始版本",
            template_schema=db_template.template_schema,
            style_config=db_template.style_config,
            created_by=current_user.id
        )
        db.add(version)
        
        db.commit()
        db.refresh(db_template)
        
        logger.info(f"推荐报告模板已创建: id={db_template.id}, name={db_template.name}, user_id={current_user.id}")
        
        return db_template
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建推荐报告模板失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建模板失败: {str(e)}"
        )


@router.get("/", response_model=List[TemplateResponse])
async def list_templates(
    skip: int = 0,
    limit: int = 100,
    is_public: Optional[bool] = None,
    is_active: Optional[bool] = True,
    created_by: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    查询推荐报告模板列表
    
    **查询参数**:
    - `is_public`: 是否公开（True=仅公开，False=仅私有，None=全部）
    - `is_active`: 是否激活（默认True）
    - `created_by`: 创建者ID（可选）
    """
    try:
        query = db.query(ResumeTemplate)
        
        # 筛选条件
        if is_public is not None:
            query = query.filter(ResumeTemplate.is_public == is_public)
        
        if is_active is not None:
            query = query.filter(ResumeTemplate.is_active == is_active)
        
        if created_by is not None:
            query = query.filter(ResumeTemplate.created_by == created_by)
        elif current_user and not current_user.is_admin:
            # 非管理员只能看到公开模板和自己创建的模板
            query = query.filter(
                (ResumeTemplate.is_public == True) | 
                (ResumeTemplate.created_by == current_user.id)
            )
        
        # 排序和分页
        templates = query.order_by(ResumeTemplate.created_at.desc()).offset(skip).limit(limit).all()
        return templates
        
    except Exception as e:
        logger.error(f"查询推荐报告模板列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询模板列表失败: {str(e)}"
        )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取推荐报告模板详情
    
    包括模板的版本历史
    """
    try:
        template = db.query(ResumeTemplate).filter(ResumeTemplate.id == template_id).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        # 权限检查：非管理员只能访问公开模板或自己创建的模板
        if current_user and not current_user.is_admin:
            if not template.is_public and template.created_by != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权访问此模板"
                )
        
        return template
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取推荐报告模板详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板详情失败: {str(e)}"
        )


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新推荐报告模板
    
    **权限要求**: 仅模板创建者和管理员
    
    **功能说明**:
    - 更新模板结构和样式
    - 自动创建新版本记录
    - 使用AI重新分析模板结构
    """
    try:
        template = db.query(ResumeTemplate).filter(ResumeTemplate.id == template_id).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        # 权限检查：只有创建者和管理员可以更新
        if template.created_by != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权更新此模板"
            )
        
        # 保存旧版本
        old_version = template.version
        old_schema = template.template_schema
        old_style = template.style_config
        
        # 更新模板
        template.name = template_data.name
        template.description = template_data.description
        template.template_schema = template_data.template_schema
        template.style_config = template_data.style_config or {}
        template.is_public = template_data.is_public
        template.updated_at = datetime.utcnow()
        
        # 版本号递增（简单版本：主版本号+1）
        try:
            version_parts = old_version.split('.')
            major_version = int(version_parts[0]) + 1
            template.version = f"{major_version}.0.0"
        except:
            template.version = "1.0.0"
        
        # 使用AI重新分析模板结构
        field_mapping = None
        try:
            # 设置用户上下文
            llm_service.set_user_context(current_user, db)
            
            # 分析模板结构
            field_mapping = await llm_service.analyze_template_structure(
                template_data.template_schema
            )
            
            # 将字段映射添加到template_schema中
            if field_mapping and isinstance(template.template_schema, dict):
                template.template_schema['field_mapping'] = field_mapping
                logger.info(f"模板 {template.id} 字段映射已更新")
        except Exception as e:
            logger.warning(f"模板 {template.id} AI分析失败: {e}")
        
        # 创建新版本记录
        version = TemplateVersion(
            template_id=template.id,
            version=template.version,
            version_name=f"更新自 {old_version}",
            template_schema=template.template_schema,
            style_config=template.style_config,
            created_by=current_user.id
        )
        db.add(version)
        
        db.commit()
        db.refresh(template)
        
        logger.info(f"推荐报告模板已更新: id={template.id}, version={template.version}, user_id={current_user.id}")
        
        return template
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新推荐报告模板失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新模板失败: {str(e)}"
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除推荐报告模板（软删除）
    
    **权限要求**: 仅模板创建者和管理员
    
    **功能说明**:
    - 软删除：设置 is_active = False
    - 不删除版本历史记录
    """
    try:
        template = db.query(ResumeTemplate).filter(ResumeTemplate.id == template_id).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        # 权限检查：只有创建者和管理员可以删除
        if template.created_by != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此模板"
            )
        
        # 软删除
        template.is_active = False
        template.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"推荐报告模板已删除（软删除）: id={template.id}, user_id={current_user.id}")
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除推荐报告模板失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除模板失败: {str(e)}"
        )


@router.get("/{template_id}/versions", response_model=List[dict])
async def get_template_versions(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    获取推荐报告模板的版本历史
    """
    try:
        template = db.query(ResumeTemplate).filter(ResumeTemplate.id == template_id).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        # 权限检查
        if current_user and not current_user.is_admin:
            if not template.is_public and template.created_by != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权访问此模板"
                )
        
        versions = db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id
        ).order_by(TemplateVersion.created_at.desc()).all()
        
        return [
            {
                "id": v.id,
                "version": v.version,
                "version_name": v.version_name,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat()
            }
            for v in versions
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板版本历史失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取版本历史失败: {str(e)}"
        )

