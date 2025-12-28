"""
文件存储服务
用于保存和管理上传的源文件
"""
import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)

class FileStorageService:
    def __init__(self):
        # 文件存储目录 - 使用uploads目录
        # 如果export_dir是"temp"，则uploads在项目根目录下
        base_dir = Path(settings.export_dir or "temp")
        if base_dir.name == "temp":
            # 如果export_dir就是"temp"，则uploads在temp的父目录下
            self.storage_dir = base_dir.parent / "uploads"
        else:
            # 否则uploads在export_dir的父目录下
            self.storage_dir = base_dir.parent / "uploads"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"文件存储目录: {self.storage_dir.absolute()}")
    
    def save_file(self, file_content: bytes, filename: str, user_id: int) -> str:
        """
        保存文件到存储目录
        返回文件路径（相对于存储目录）
        """
        # 生成文件hash作为文件名的一部分，避免冲突
        file_hash = hashlib.md5(file_content).hexdigest()[:8]
        file_ext = Path(filename).suffix
        safe_filename = f"{user_id}_{file_hash}_{Path(filename).stem}{file_ext}"
        
        # 确保文件名安全
        safe_filename = "".join(c for c in safe_filename if c.isalnum() or c in "._-")
        
        file_path = self.storage_dir / safe_filename
        file_path.write_bytes(file_content)
        
        logger.info(f"文件已保存: {file_path}")
        return str(file_path.relative_to(self.storage_dir.parent))
    
    def get_file_path(self, file_path: str) -> Optional[Path]:
        """
        获取文件的完整路径
        """
        full_path = self.storage_dir.parent / file_path
        if full_path.exists() and full_path.is_file():
            return full_path
        return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除文件
        """
        try:
            full_path = self.storage_dir.parent / file_path
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
                logger.info(f"文件已删除: {full_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在
        """
        full_path = self.storage_dir.parent / file_path
        return full_path.exists() and full_path.is_file()

# 全局文件存储服务实例
file_storage_service = FileStorageService()

