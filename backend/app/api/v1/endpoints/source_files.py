"""
原始简历文件管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from ....core.database import get_db
from ....models.resume import SourceFile, ParsedResume, CandidateResume
from ....models.user import User
from ....api.v1.endpoints.users import get_current_user
from ....services.file_storage import file_storage_service
from ....schemas.resume import SourceFileResponse, SourceFileListResponse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[SourceFileListResponse])
async def get_source_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索关键词（文件名）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取原始简历文件列表（管理员可以看到所有数据，普通用户只能看到自己的）"""
    # 管理员可以看到所有数据，普通用户只能看到自己的
    if current_user.user_type == "super_admin":
        query = db.query(SourceFile)
    else:
        query = db.query(SourceFile).filter(SourceFile.user_id == current_user.id)
    
    # 搜索功能
    if search:
        query = query.filter(SourceFile.file_name.contains(search))
    
    # 按创建时间倒序（使用复合索引 idx_source_file_user_created 优化）
    query = query.order_by(SourceFile.created_at.desc())
    
    # 性能优化：直接执行分页查询（列表查询不需要总数）
    files = query.offset(skip).limit(limit).all()
    
    return files

@router.get("/{file_id}", response_model=SourceFileResponse)
async def get_source_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取原始简历文件详情（管理员可以查看所有数据，普通用户只能查看自己的）"""
    # 管理员可以查看所有数据，普通用户只能查看自己的
    if current_user.user_type == "super_admin":
        file = db.query(SourceFile).filter(SourceFile.id == file_id).first()
    else:
        file = db.query(SourceFile).filter(
            SourceFile.id == file_id,
            SourceFile.user_id == current_user.id
        ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return file

@router.get("/{file_id}/download")
async def download_source_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """下载原始简历文件（管理员可以下载所有文件，普通用户只能下载自己的文件）"""
    # 管理员可以下载所有文件，普通用户只能下载自己的文件
    if current_user.user_type == "super_admin":
        file = db.query(SourceFile).filter(SourceFile.id == file_id).first()
    else:
        file = db.query(SourceFile).filter(
            SourceFile.id == file_id,
            SourceFile.user_id == current_user.id
        ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 从文件存储服务获取文件
    file_path = file_storage_service.get_file_path(file.file_path)
    
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或已被删除")
    
    # 确定媒体类型
    media_type = "application/pdf"
    if file.file_type:
        if "pdf" in file.file_type.lower():
            media_type = "application/pdf"
        elif "word" in file.file_type.lower() or "docx" in file.file_type.lower():
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif "doc" in file.file_type.lower():
            media_type = "application/msword"
    
    return FileResponse(
        path=str(file_path),
        filename=file.file_name,
        media_type=media_type
    )

@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除原始简历文件（管理员可以删除所有数据，普通用户只能删除自己的数据）
    
    注意：解析结果和推荐报告一旦生成后就是独立的，删除原始简历不会影响已生成的数据。
    解析结果和推荐报告中的数据已经完整保存，不依赖原始简历文件。
    """
    # 管理员可以删除所有数据，普通用户只能删除自己的数据
    if current_user.user_type == "super_admin":
        file = db.query(SourceFile).filter(SourceFile.id == file_id).first()
    else:
        file = db.query(SourceFile).filter(
            SourceFile.id == file_id,
            SourceFile.user_id == current_user.id
        ).first()
    
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 记录关联信息（仅用于日志，不影响删除）
    if current_user.user_type == "super_admin":
        related_parsed_resumes = db.query(ParsedResume).filter(
            ParsedResume.file_hash == file.file_hash
        ).count()
        related_candidate_resumes = db.query(CandidateResume).filter(
            CandidateResume.source_file_path == file.file_path
        ).count()
    else:
        related_parsed_resumes = db.query(ParsedResume).filter(
            ParsedResume.file_hash == file.file_hash,
            ParsedResume.user_id == current_user.id
        ).count()
        related_candidate_resumes = db.query(CandidateResume).filter(
            CandidateResume.source_file_path == file.file_path,
            CandidateResume.user_id == current_user.id
        ).count()
    
    # 直接删除，不检查依赖（解析结果和推荐报告已独立，不依赖原始简历）
    # 注意：这里不删除物理文件，只删除数据库记录，保留文件以便其他关联数据使用
    # 如果需要删除物理文件，可以取消下面的注释：
    # file_path = file_storage_service.get_file_path(file.file_path)
    # if file_path and file_path.exists():
    #     file_path.unlink()
    
    try:
        db.delete(file)
        db.commit()
        logger.info(f"用户 {current_user.id} 删除了源文件 {file_id}，关联的解析结果数量：{related_parsed_resumes}，推荐报告数量：{related_candidate_resumes}（已独立，不受影响）")
    except Exception as e:
        db.rollback()
        logger.error(f"删除源文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)
