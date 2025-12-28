"""
密码强度验证模块
"""
import re
from typing import Tuple


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    验证密码强度
    
    Args:
        password: 待验证的密码
        
    Returns:
        (is_valid, error_message): 是否有效和错误信息
    """
    if not password:
        return False, "密码不能为空"
    
    # 检查长度
    if len(password) < 8:
        return False, "密码长度至少8位"
    
    if len(password.encode("utf-8")) > 72:
        return False, "密码过长，最大72字符（bcrypt限制）"
    
    # 检查是否包含字母
    if not re.search(r'[A-Za-z]', password):
        return False, "密码必须包含至少一个字母"
    
    # 检查是否包含数字
    if not re.search(r'[0-9]', password):
        return False, "密码必须包含至少一个数字"
    
    # 可选：检查是否包含特殊字符（可选要求）
    # if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
    #     return False, "密码必须包含至少一个特殊字符"
    
    return True, ""


def get_password_strength_score(password: str) -> int:
    """
    计算密码强度分数 (0-5)
    
    Returns:
        强度分数：0-5，5为最强
    """
    score = 0
    
    # 长度得分
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    
    # 包含小写字母
    if re.search(r'[a-z]', password):
        score += 1
    
    # 包含大写字母
    if re.search(r'[A-Z]', password):
        score += 1
    
    # 包含数字
    if re.search(r'[0-9]', password):
        score += 1
    
    # 包含特殊字符
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    
    return min(score, 5)

