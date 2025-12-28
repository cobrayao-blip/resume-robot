"""
批量操作API端点
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from ....core.database import get_db
from ....models.user import User
from ....models.job import JobPosition
from ....api.v1.endpoints.users import get_current_user
from ....services.batch_service import BatchService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload-and-parse", status_code=status.HTTP_200_OK)
async def batch_upload_and_parse(
    files: List[UploadFile] = File(..., description="简历文件列表（PDF或Word格式）"),
    job_id: Optional[int] = Form(None, description="岗位ID（可选，如果提供则直接关联到岗位）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量上传并解析简历"""
    try:
        if not files:
            raise HTTPException(status_code=400, detail="请至少上传一个文件")
        
        # 验证文件类型
        allowed_extensions = {".pdf", ".doc", ".docx"}
        for file in files:
            if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的文件类型: {file.filename}，仅支持PDF和Word格式"
                )
        
        # 验证岗位是否存在
        if job_id:
            job = db.query(JobPosition).filter(JobPosition.id == job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="岗位不存在")
        
        # 执行批量上传和解析
        batch_service = BatchService(db_session=db)
        result = await batch_service.batch_upload_and_parse(
            files=files,
            user_id=current_user.id,
            job_id=job_id
        )
        
        logger.info(f"批量上传解析完成: total={result['total']}, success={result['success']}, failed={result['failed']}, user_id={current_user.id}")
        return {
            "success": True,
            "data": result,
            "message": f"批量上传解析完成: 共{result['total']}个文件，成功{result['success']}个，失败{result['failed']}个"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量上传解析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量上传解析失败: {str(e)}")


@router.post("/match-to-job", status_code=status.HTTP_200_OK)
async def batch_match_to_job(
    resume_ids: List[int] = Query(..., description="简历ID列表"),
    job_id: int = Query(..., description="岗位ID"),
    resume_type: str = Query("parsed", description="简历类型: parsed/candidate"),
    match_model_id: Optional[int] = Query(None, description="匹配模型ID"),
    auto_filter: bool = Query(True, description="是否自动执行预筛选（只匹配通过预筛选的简历）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量匹配简历与岗位"""
    try:
        # 验证岗位是否存在
        job = db.query(JobPosition).filter(JobPosition.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        
        # 执行批量匹配
        batch_service = BatchService(db_session=db)
        result = await batch_service.batch_match_resumes_to_job(
            resume_ids=resume_ids,
            job_id=job_id,
            resume_type=resume_type,
            match_model_id=match_model_id,
            auto_filter=auto_filter
        )
        
        logger.info(
            f"批量匹配完成: job_id={job_id}, total={result['total']}, success={result['success']}, "
            f"strongly_recommended={result['summary']['strongly_recommended']}, "
            f"recommended={result['summary']['recommended']}, user_id={current_user.id}"
        )
        return {
            "success": True,
            "data": result,
            "message": f"批量匹配完成: 共{result['total']}份简历，成功{result['success']}份"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量匹配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量匹配失败: {str(e)}")


@router.post("/generate-reports", status_code=status.HTTP_200_OK)
async def batch_generate_reports(
    match_ids: List[int] = Query(..., description="匹配记录ID列表"),
    template_id: int = Query(..., description="模板ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量生成推荐报告"""
    try:
        from ....models.resume import ResumeTemplate
        
        # 验证模板是否存在
        template = db.query(ResumeTemplate).filter(ResumeTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        # 执行批量生成
        batch_service = BatchService(db_session=db)
        result = await batch_service.batch_generate_reports(
            match_ids=match_ids,
            template_id=template_id,
            user_id=current_user.id
        )
        
        logger.info(
            f"批量生成报告完成: template_id={template_id}, total={result['total']}, "
            f"success={result['success']}, failed={result['failed']}, user_id={current_user.id}"
        )
        return {
            "success": True,
            "data": result,
            "message": f"批量生成报告完成: 共{result['total']}个，成功{result['success']}个，失败{result['failed']}个"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量生成报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量生成报告失败: {str(e)}")


@router.get("/upload-progress/{task_id}", status_code=status.HTTP_200_OK)
async def get_upload_progress(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取批量上传进度（TODO: 实现任务队列后使用）"""
    # TODO: 实现任务队列（Celery）后，这里返回任务进度
    return {
        "success": True,
        "data": {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "message": "任务已完成"
        }
    }


@router.get("/match-progress/{task_id}", status_code=status.HTTP_200_OK)
async def get_match_progress(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取批量匹配进度（TODO: 实现任务队列后使用）"""
    # TODO: 实现任务队列（Celery）后，这里返回任务进度
    return {
        "success": True,
        "data": {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "message": "任务已完成"
        }
    }

