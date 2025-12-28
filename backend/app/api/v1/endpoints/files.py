"""
源文件管理API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from ....core.database import get_db
from ....models.resume import CandidateResume
from ....models.user import User
from ....api.v1.endpoints.users import get_current_user
from ....services.file_storage import file_storage_service
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/resumes/{resume_id}/source-file")
async def get_source_file(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取简历的源文件
    """
    resume = db.query(CandidateResume).filter(
        CandidateResume.id == resume_id,
        CandidateResume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    if not resume.source_file_name:
        raise HTTPException(status_code=404, detail="该简历没有源文件")
    
    # 从文件存储服务获取文件
    file_path = None
    if resume.source_file_path:
        file_path = file_storage_service.get_file_path(resume.source_file_path)
    
    # 如果文件不存在，返回404
    # 注意：对于旧数据，文件可能不存在，这是正常的
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="源文件不存在或已被删除。注意：旧版本的简历可能没有保存源文件。")
    
    # 确定媒体类型
    media_type = "application/pdf"
    if resume.source_file_type:
        if "word" in resume.source_file_type.lower() or "docx" in resume.source_file_type.lower():
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif "doc" in resume.source_file_type.lower():
            media_type = "application/msword"
    
    return FileResponse(
        path=str(file_path),
        filename=resume.source_file_name,
        media_type=media_type
    )

@router.delete("/resumes/{resume_id}/source-file")
async def delete_source_file(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除简历的源文件
    """
    resume = db.query(CandidateResume).filter(
        CandidateResume.id == resume_id,
        CandidateResume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    if not resume.source_file_name:
        raise HTTPException(status_code=404, detail="该简历没有源文件")
    
    # 删除文件
    deleted = False
    if resume.source_file_path:
        deleted = file_storage_service.delete_file(resume.source_file_path)
    
    # 清除数据库中的源文件信息
    resume.source_file_name = None
    resume.source_file_type = None
    resume.source_file_path = None
    
    db.commit()
    
    return {"success": True, "message": "源文件已删除"}

@router.get("/resumes/{resume_id}/source-file-info")
async def get_source_file_info(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取简历的源文件信息（不下载文件）
    """
    resume = db.query(CandidateResume).filter(
        CandidateResume.id == resume_id,
        CandidateResume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    
    file_exists = False
    if resume.source_file_name and resume.source_file_path:
        file_exists = file_storage_service.file_exists(resume.source_file_path)
    
    return {
        "file_name": resume.source_file_name,
        "file_type": resume.source_file_type,
        "file_exists": file_exists,
        "created_at": resume.created_at.isoformat() if resume.created_at else None
    }

