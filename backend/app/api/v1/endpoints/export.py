from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
from ....core.database import get_db
from ....core.usage_limit import check_usage_limit, increment_usage
from ....models.user import User
from ....api.v1.endpoints.users import get_current_user
import logging
from ....services.word_exporter import word_exporter
from ....schemas.resume import ExportPayload

router = APIRouter()

@router.post("/export-word")
async def export_resume_to_word(
    resume_data: ExportPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_usage_limit())
):
    """
    导出简历为Word文档（会检查并消耗使用次数）
    """
    try:
        # 导出Word文档（确保不丢可选字段）
        data = resume_data.dict(exclude_none=False) if hasattr(resume_data, 'dict') else resume_data.model_dump(exclude_none=False)
        logger = logging.getLogger(__name__)
        logger.info(
            "Export payload keys: %s; sections_type=%s sections_len=%s",
            list(data.keys()),
            type(data.get('template_sections')).__name__ if isinstance(data, dict) else None,
            len(data.get('template_sections')) if isinstance(data, dict) and isinstance(data.get('template_sections'), list) else 0,
        )
        
        # 导出Word文档
        file_path = word_exporter.export_resume(data)
        
        # 只有在导出成功后才增加使用次数
        # 刷新用户对象以确保获取最新的使用次数
        db.refresh(current_user)
        increment_usage(db, current_user)
        logger.info(f"[导出Word] 用户 {current_user.id} 使用次数已更新: {current_user.current_month_usage}/{current_user.monthly_usage_limit}")
        
        # 获取文件名
        filename = os.path.basename(file_path)
        
        # 返回文件下载
        response = FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        # 下载完成后异步清理临时文件
        background_tasks.add_task(lambda p: os.path.exists(p) and os.remove(p), file_path)
        return response
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"[导出Word] 导出失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")

@router.post("/preview-word")
async def preview_resume_word(
    resume_data: ExportPayload,
    db: Session = Depends(get_db)
):
    """
    预览Word文档生成（返回文档信息）
    """
    try:
        # 这里可以返回文档的预览信息，而不是直接下载
        # 比如文档大小、页数估计等
        data = resume_data.dict(exclude_none=False) if hasattr(resume_data, 'dict') else resume_data.model_dump(exclude_none=False)
        file_path = word_exporter.export_resume(data)
        file_size = os.path.getsize(file_path)
        
        return {
            "success": True,
            "filename": os.path.basename(file_path),
            "file_size": file_size,
            "download_url": f"/api/v1/export/export-word"  # 实际下载URL
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")