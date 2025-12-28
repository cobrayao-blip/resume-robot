"""
文件验证工具
通过检查文件头（Magic Number）验证文件真实类型
"""
import logging
from typing import Optional, Tuple
from ..core.constants import ALLOWED_FILE_TYPES, ALLOWED_FILE_EXTENSIONS

logger = logging.getLogger(__name__)

# 文件头签名（Magic Numbers）
FILE_SIGNATURES = {
    # PDF: %PDF
    b'\x25\x50\x44\x46': 'application/pdf',
    # DOCX: PK\x03\x04 (ZIP格式)
    b'\x50\x4B\x03\x04': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    # DOC: 旧版Word文档（多种格式）
    b'\xD0\xCF\x11\xE0': 'application/msword',  # OLE2格式
    b'\x0E\x11\xFC\x0D': 'application/msword',  # 另一种格式
    b'\xCF\x11\xE0\xA1': 'application/msword',  # 另一种格式
}

# 文件扩展名到MIME类型的映射
EXTENSION_TO_MIME = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
}


def validate_file_content(file_content: bytes, filename: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    通过文件头验证文件真实类型
    
    Args:
        file_content: 文件内容（字节）
        filename: 文件名（可选，用于扩展名检查）
        
    Returns:
        (is_valid, detected_mime_type, error_message)
        - is_valid: 是否有效
        - detected_mime_type: 检测到的MIME类型
        - error_message: 错误消息（如果无效）
    """
    if not file_content or len(file_content) < 4:
        return False, None, "文件内容为空或过小"
    
    # 检查文件头
    file_header = file_content[:4]
    detected_mime = None
    
    # 检查所有已知的文件签名
    for signature, mime_type in FILE_SIGNATURES.items():
        if file_content.startswith(signature):
            detected_mime = mime_type
            break
    
    # 对于DOCX，需要进一步验证（因为DOCX是ZIP格式）
    if file_content.startswith(b'\x50\x4B\x03\x04'):
        # 检查ZIP文件是否包含Word文档结构
        # DOCX文件在ZIP中应该包含 [Content_Types].xml
        try:
            # 简单检查：查找Word文档的典型内容
            if b'word/' in file_content[:1024] or b'[Content_Types].xml' in file_content[:2048]:
                detected_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            else:
                # 可能是其他ZIP格式文件
                detected_mime = None
        except Exception:
            pass
    
    # 如果通过文件头检测到类型
    if detected_mime:
        if detected_mime in ALLOWED_FILE_TYPES:
            return True, detected_mime, None
        else:
            return False, detected_mime, f"不支持的文件类型: {detected_mime}"
    
    # 如果文件头检测失败，尝试通过扩展名判断（作为备用方案）
    if filename:
        ext = filename.lower()
        for allowed_ext in ALLOWED_FILE_EXTENSIONS:
            if ext.endswith(allowed_ext):
                mime_from_ext = EXTENSION_TO_MIME.get(allowed_ext)
                if mime_from_ext:
                    logger.warning(f"无法通过文件头验证文件类型，使用扩展名判断: {filename}")
                    return True, mime_from_ext, None
    
    return False, None, "无法识别文件类型，可能不是支持的格式（PDF或Word文档）"


def validate_file_type(content_type: str, file_content: bytes, filename: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    验证文件类型（结合content_type和文件内容）
    
    Args:
        content_type: HTTP Content-Type
        file_content: 文件内容
        filename: 文件名
        
    Returns:
        (is_valid, error_message)
    """
    # 首先检查content_type是否在允许列表中
    if content_type not in ALLOWED_FILE_TYPES:
        return False, f"不支持的文件类型: {content_type}"
    
    # 然后验证文件内容
    is_valid, detected_mime, error_msg = validate_file_content(file_content, filename)
    
    if not is_valid:
        return False, error_msg or "文件内容验证失败"
    
    # 验证content_type和检测到的MIME类型是否匹配
    if detected_mime and detected_mime != content_type:
        logger.warning(
            f"文件类型不匹配: Content-Type={content_type}, "
            f"检测到的类型={detected_mime}, 文件名={filename}"
        )
        # 对于DOC和DOCX，允许一定程度的宽松（因为旧版Word格式复杂）
        if 'msword' in content_type or 'msword' in detected_mime:
            return True, None
        # 其他情况，使用检测到的类型
        return True, None
    
    return True, None

