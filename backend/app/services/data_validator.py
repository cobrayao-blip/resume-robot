"""
数据验证和纠错服务
使用AI进行智能数据验证和自动纠错
"""
import logging
from typing import Dict, Any, List, Optional
from .deepseek_service import deepseek_service
import json
import re

logger = logging.getLogger(__name__)

class DataValidator:
    """数据验证和纠错服务"""
    
    def __init__(self, deepseek_service_instance=None):
        """初始化，支持传入deepseek_service实例"""
        self.deepseek_service = deepseek_service_instance or deepseek_service
    
    async def validate_and_correct(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证数据并自动纠错
        返回：{
            "corrected_data": {...},  # 纠错后的数据
            "corrections": [...],     # 纠错记录
            "warnings": [...]         # 警告信息
        }
        """
        corrections = []
        warnings = []
        corrected_data = json.loads(json.dumps(parsed_data))  # 深拷贝
        
        # 1. 基本信息验证和纠错
        basic_info = corrected_data.get('basic_info', {})
        if basic_info:
            # 电话格式标准化
            phone = basic_info.get('phone', '')
            if phone:
                normalized_phone = self._normalize_phone(phone)
                if normalized_phone != phone:
                    corrections.append({
                        "field": "basic_info.phone",
                        "original": phone,
                        "corrected": normalized_phone,
                        "reason": "电话格式标准化"
                    })
                    basic_info['phone'] = normalized_phone
            
            # 邮箱格式验证
            email = basic_info.get('email', '')
            if email and not self._is_valid_email(email):
                warnings.append({
                    "field": "basic_info.email",
                    "value": email,
                    "message": "邮箱格式可能不正确"
                })
        
        # 2. 工作经历验证和纠错
        work_experiences = corrected_data.get('work_experiences', [])
        for idx, exp in enumerate(work_experiences):
            # 时间格式标准化
            start_date = exp.get('start_date', '')
            if start_date:
                normalized_start = self._normalize_date(start_date)
                if normalized_start != start_date:
                    corrections.append({
                        "field": f"work_experiences[{idx}].start_date",
                        "original": start_date,
                        "corrected": normalized_start,
                        "reason": "时间格式标准化"
                    })
                    exp['start_date'] = normalized_start
            
            end_date = exp.get('end_date', '')
            if end_date:
                normalized_end = self._normalize_date(end_date)
                if normalized_end != end_date:
                    corrections.append({
                        "field": f"work_experiences[{idx}].end_date",
                        "original": end_date,
                        "corrected": normalized_end,
                        "reason": "时间格式标准化"
                    })
                    exp['end_date'] = normalized_end
            
            # 检查时间逻辑
            if start_date and end_date and not exp.get('is_current'):
                if normalized_start > normalized_end:
                    warnings.append({
                        "field": f"work_experiences[{idx}]",
                        "message": f"开始时间({normalized_start})晚于结束时间({normalized_end})，请检查"
                    })
            
            # 公司名称标准化（去除多余空格、统一格式）
            company = exp.get('company', '')
            if company:
                normalized_company = self._normalize_company_name(company)
                if normalized_company != company:
                    corrections.append({
                        "field": f"work_experiences[{idx}].company",
                        "original": company,
                        "corrected": normalized_company,
                        "reason": "公司名称格式标准化"
                    })
                    exp['company'] = normalized_company
        
        # 3. 教育背景验证和纠错
        education = corrected_data.get('education', [])
        for idx, edu in enumerate(education):
            # 入学时间格式标准化
            start_date = edu.get('start_date', '')
            if start_date:
                normalized_start = self._normalize_date(start_date)
                if normalized_start != start_date:
                    corrections.append({
                        "field": f"education[{idx}].start_date",
                        "original": start_date,
                        "corrected": normalized_start,
                        "reason": "时间格式标准化"
                    })
                    edu['start_date'] = normalized_start
            
            # 毕业时间格式标准化（end_date优先，如果没有则使用graduation_date）
            end_date = edu.get('end_date', '')
            grad_date = edu.get('graduation_date', '')
            
            # 如果只有graduation_date，将其同步到end_date
            if not end_date and grad_date:
                edu['end_date'] = grad_date
                end_date = grad_date
            
            if end_date:
                normalized_end = self._normalize_date(end_date)
                if normalized_end != end_date:
                    corrections.append({
                        "field": f"education[{idx}].end_date",
                        "original": end_date,
                        "corrected": normalized_end,
                        "reason": "时间格式标准化"
                    })
                    edu['end_date'] = normalized_end
                    # 同时更新graduation_date（如果存在）
                    if grad_date:
                        edu['graduation_date'] = normalized_end
            
            # 如果只有graduation_date，也进行标准化
            if grad_date and not end_date:
                normalized_grad = self._normalize_date(grad_date)
                if normalized_grad != grad_date:
                    corrections.append({
                        "field": f"education[{idx}].graduation_date",
                        "original": grad_date,
                        "corrected": normalized_grad,
                        "reason": "时间格式标准化"
                    })
                    edu['graduation_date'] = normalized_grad
            
            # 学位标准化
            degree = edu.get('degree', '')
            if degree:
                normalized_degree = self._normalize_degree(degree)
                if normalized_degree != degree:
                    corrections.append({
                        "field": f"education[{idx}].degree",
                        "original": degree,
                        "corrected": normalized_degree,
                        "reason": "学位名称标准化"
                    })
                    edu['degree'] = normalized_degree
        
        # 4. 使用AI进行智能验证和纠错
        try:
            ai_corrections = await self._ai_validate_and_correct(corrected_data)
            if ai_corrections:
                corrections.extend(ai_corrections.get('corrections', []))
                warnings.extend(ai_corrections.get('warnings', []))
                # 应用AI纠错
                if 'corrected_data' in ai_corrections:
                    corrected_data = ai_corrections['corrected_data']
        except Exception as e:
            logger.warning(f"AI验证和纠错失败（不影响主流程）: {e}")
        
        return {
            "corrected_data": corrected_data,
            "corrections": corrections,
            "warnings": warnings
        }
    
    def _normalize_phone(self, phone: str) -> str:
        """标准化电话格式"""
        # 移除所有非数字字符（保留+号）
        phone = re.sub(r'[^\d+]', '', phone)
        # 如果是11位数字，添加分隔符：138-1234-5678
        if len(phone) == 11 and phone.isdigit():
            return f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
        return phone
    
    def _is_valid_email(self, email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _normalize_date(self, date_str: str) -> str:
        """标准化日期格式为 YYYY-MM"""
        if not date_str:
            return date_str
        
        # 尝试匹配各种日期格式
        patterns = [
            (r'(\d{4})[年.-](\d{1,2})[月.-]?', r'\1-\2'),  # 2020年1月 -> 2020-01
            (r'(\d{4})[/-](\d{1,2})[/-]?', r'\1-\2'),      # 2020/01 -> 2020-01
            (r'(\d{4})\.(\d{1,2})\.?', r'\1-\2'),          # 2020.01 -> 2020-01
        ]
        
        for pattern, replacement in patterns:
            match = re.search(pattern, date_str)
            if match:
                year = match.group(1)
                month = match.group(2).zfill(2)  # 补零
                return f"{year}-{month}"
        
        # 如果已经是 YYYY-MM 格式，直接返回
        if re.match(r'^\d{4}-\d{2}$', date_str):
            return date_str
        
        return date_str  # 无法识别则返回原值
    
    def _normalize_company_name(self, company: str) -> str:
        """标准化公司名称"""
        # 去除首尾空格
        company = company.strip()
        # 统一空格（多个空格变为一个）
        company = re.sub(r'\s+', ' ', company)
        return company
    
    def _normalize_degree(self, degree: str) -> str:
        """标准化学位名称"""
        degree_map = {
            '本科': '本科',
            '学士': '本科',
            'Bachelor': '本科',
            '本科毕业': '本科',
            '硕士': '硕士',
            '研究生': '硕士',
            'Master': '硕士',
            '硕士毕业': '硕士',
            '博士': '博士',
            'PhD': '博士',
            '博士毕业': '博士',
            '专科': '专科',
            '大专': '专科',
        }
        return degree_map.get(degree, degree)
    
    async def _ai_validate_and_correct(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """使用AI进行智能验证和纠错"""
        system_prompt = """你是一位数据质量专家。你的任务是验证简历数据的合理性和准确性，并识别可能的错误。

验证重点：
1. **时间逻辑**：检查工作经历时间是否合理、是否重叠
2. **数据一致性**：检查数据是否自相矛盾
3. **格式规范**：检查格式是否符合规范
4. **内容合理性**：检查内容是否合理（如工作年限、职位晋升等）

输出格式（JSON）：
{
    "corrections": [
        {
            "field": "字段路径",
            "original": "原始值",
            "corrected": "纠正后的值",
            "reason": "纠正原因"
        }
    ],
    "warnings": [
        {
            "field": "字段路径",
            "message": "警告信息"
        }
    ],
    "corrected_data": {...}  // 纠正后的完整数据（可选）
}"""

        data_json = json.dumps(data, ensure_ascii=False, indent=2)
        user_prompt = f"""请验证以下简历数据的合理性和准确性，识别并纠正可能的错误。

简历数据：
{data_json}

请重点检查：
1. 时间逻辑是否合理（工作经历时间是否重叠、是否合理）
2. 数据是否自相矛盾
3. 格式是否符合规范
4. 内容是否合理

如果发现错误，请提供纠正建议。直接输出JSON结果："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # 增加max_tokens到8192（DeepSeek上限），确保复杂简历的完整JSON响应不被截断
            response = await self.deepseek_service.chat_completion(messages, temperature=0.1, max_tokens=8192)
            result = self.deepseek_service._parse_json_response(response)
            return result
        except Exception as e:
            logger.warning(f"AI验证失败: {e}")
            return {"corrections": [], "warnings": []}

# 全局实例
data_validator = DataValidator()

