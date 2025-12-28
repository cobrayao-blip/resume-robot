"""
Prompt构建服务 - 统一管理所有LLM Prompt的构建
整合组织架构信息，提升Prompt质量
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models.job import JobPosition, CompanyInfo
from ..models.department import Department

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Prompt构建服务 - 统一管理所有LLM Prompt的构建"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def build_company_context(self, tenant_id: int) -> str:
        """
        构建公司上下文
        
        Args:
            tenant_id: 租户ID
        
        Returns:
            公司上下文字符串
        """
        company = self.db.query(CompanyInfo).filter(
            CompanyInfo.tenant_id == tenant_id
        ).first()
        
        if not company:
            return ""
        
        parts = []
        parts.append("## 公司信息")
        parts.append(f"公司名称: {company.name}")
        
        if company.industry:
            parts.append(f"所属行业: {company.industry}")
        if company.products:
            parts.append(f"主要产品/服务: {company.products}")
        if company.application_scenarios:
            parts.append(f"应用场景: {company.application_scenarios}")
        if company.company_culture:
            parts.append(f"公司文化: {company.company_culture}")
        if company.preferences:
            parts.append(f"招聘偏好: {company.preferences}")
        
        # 新增字段
        if company.company_size:
            parts.append(f"公司规模: {company.company_size}")
        if company.development_stage:
            parts.append(f"发展阶段: {company.development_stage}")
        if company.business_model:
            parts.append(f"商业模式: {company.business_model}")
        if company.core_values:
            parts.append(f"核心价值观: {company.core_values}")
        if company.recruitment_philosophy:
            parts.append(f"招聘理念: {company.recruitment_philosophy}")
        
        return "\n".join(parts)
    
    def build_department_context(self, department_id: Optional[int]) -> str:
        """
        构建部门上下文（包含组织架构信息）
        
        Args:
            department_id: 部门ID
        
        Returns:
            部门上下文字符串
        """
        if not department_id:
            return ""
        
        department = self.db.query(Department).filter(
            Department.id == department_id
        ).first()
        
        if not department:
            return ""
        
        parts = []
        parts.append("## 部门信息")
        parts.append(f"部门名称: {department.name}")
        
        # 组织架构信息
        if department.path:
            parts.append(f"部门路径: {department.path}")
        if department.level:
            parts.append(f"部门层级: {department.level}级部门")
        if department.parent_id:
            parent = self.db.query(Department).filter(Department.id == department.parent_id).first()
            if parent:
                parts.append(f"上级部门: {parent.name}")
        
        # 部门职责和文化
        if department.description:
            parts.append(f"部门职责: {department.description}")
        if department.key_responsibilities:
            parts.append(f"核心职责: {department.key_responsibilities}")
        if department.department_culture:
            parts.append(f"部门文化: {department.department_culture}")
        if department.work_style:
            parts.append(f"工作风格: {department.work_style}")
        if department.team_size:
            parts.append(f"团队规模: {department.team_size}人")
        
        return "\n".join(parts)
    
    def build_job_context(self, job: JobPosition) -> str:
        """
        构建岗位上下文
        
        Args:
            job: 岗位对象
        
        Returns:
            岗位上下文字符串
        """
        parts = []
        parts.append("## 岗位信息")
        parts.append(f"岗位名称: {job.title}")
        
        # 部门信息（优先使用department_id关联的部门）
        if job.department_id:
            dept_context = self.build_department_context(job.department_id)
            if dept_context:
                parts.append(dept_context)
        elif job.department:
            parts.append(f"部门: {job.department}")
        
        if job.description:
            parts.append(f"岗位描述:\n{job.description}")
        if job.requirements:
            parts.append(f"岗位要求:\n{job.requirements}")
        
        return "\n".join(parts)
    
    def build_match_analysis_prompt(
        self,
        resume_data: Dict[str, Any],
        job: JobPosition,
        job_parsed_data: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[int] = None
    ) -> str:
        """
        构建简历匹配分析Prompt（完整版）
        
        Args:
            resume_data: 简历数据
            job: 岗位对象
            job_parsed_data: 岗位画像数据（可选）
            tenant_id: 租户ID（用于获取公司信息）
        
        Returns:
            完整的匹配分析Prompt
        """
        prompt_parts = []
        
        # 1. 公司信息上下文
        if tenant_id:
            company_context = self.build_company_context(tenant_id)
            if company_context:
                prompt_parts.append(company_context)
                prompt_parts.append("")
        
        # 2. 岗位上下文（包含部门信息）
        job_context = self.build_job_context(job)
        if job_context:
            prompt_parts.append(job_context)
            prompt_parts.append("")
        
        # 3. 岗位画像（如果提供）
        if job_parsed_data:
            prompt_parts.append("## 岗位画像（结构化）")
            import json
            prompt_parts.append(json.dumps(job_parsed_data, ensure_ascii=False, indent=2))
            prompt_parts.append("")
        
        # 4. 候选人简历
        prompt_parts.append("## 候选人简历")
        import json
        prompt_parts.append(json.dumps(resume_data, ensure_ascii=False, indent=2))
        prompt_parts.append("")
        
        # 5. 分析要求
        prompt_parts.append("## 分析要求")
        prompt_parts.append("""
请根据以上信息，对候选人进行深度匹配分析，包括：

1. **技能匹配度**：评估候选人的技能是否满足岗位要求
2. **经验匹配度**：评估候选人的工作经验是否匹配岗位需求
3. **组织匹配度**：评估候选人是否适合该部门/团队（考虑部门文化、工作风格）
4. **文化匹配度**：评估候选人是否匹配公司/部门文化
5. **风险点识别**：识别可能的风险点（如：跳槽频繁、技能不匹配、文化不匹配等）
6. **综合评分**：给出0-10分的综合匹配分数

请特别关注：
- 组织架构信息：理解岗位在组织中的位置和作用
- 部门文化：考虑部门文化对候选人的要求
- 公司文化：考虑公司文化对候选人的要求
- 组织匹配：评估候选人是否适合该组织环境

输出JSON格式：
""")
        
        # JSON格式定义
        prompt_parts.append("""
{
  "score": 8.5,  // 综合匹配分数（0-10）
  "strengths": [
    "具有丰富的Python开发经验",
    "熟悉Django框架"
  ],
  "weaknesses": [
    "缺少大型项目经验"
  ],
  "risk_points": [
    "跳槽频繁"
  ],
  "organization_match": {
    "score": 8.0,  // 组织匹配分数
    "analysis": "候选人具有团队合作精神，适合该部门的工作风格"
  },
  "culture_match": {
    "score": 8.5,  // 文化匹配分数
    "analysis": "候选人的价值观与公司核心价值观匹配"
  },
  "recommendation": "强烈推荐",  // 推荐等级：强烈推荐/推荐/谨慎推荐/不推荐
  "detailed_analysis": "候选人具有5年Python开发经验，熟练掌握Django框架和PostgreSQL数据库。曾在XX公司负责核心业务系统开发，具备良好的技术能力和项目经验。虽然缺少微服务架构经验，但学习能力强，可以快速适应。"
}
""")
        
        return "\n".join(prompt_parts)
    
    def build_job_parsing_prompt(
        self,
        job: JobPosition,
        tenant_id: Optional[int] = None
    ) -> str:
        """
        构建岗位解析Prompt（完整版）
        
        Args:
            job: 岗位对象
            tenant_id: 租户ID（用于获取公司信息）
        
        Returns:
            完整的岗位解析Prompt
        """
        prompt_parts = []
        
        # 1. 公司信息上下文
        if tenant_id:
            company_context = self.build_company_context(tenant_id)
            if company_context:
                prompt_parts.append(company_context)
                prompt_parts.append("")
        
        # 2. 岗位上下文（包含部门信息）
        job_context = self.build_job_context(job)
        if job_context:
            prompt_parts.append(job_context)
            prompt_parts.append("")
        
        # 3. 输出要求
        prompt_parts.append("## 输出要求")
        prompt_parts.append("""
请根据以上信息，提取结构化的岗位画像，包括：

1. **岗位要求**：
   - 学历要求
   - 工作经验要求
   - 技能要求（技术栈、工具、框架）
   - 相关领域经验
   - 年龄要求（如有）
   - 地点要求（如有）

2. **岗位特点**：
   - 核心职责
   - 工作内容
   - 发展前景

3. **偏好信息**：
   - 公司对候选人的偏好（如：可靠性、创新性、团队合作等）

4. **组织匹配要求**：
   - 部门文化匹配要求
   - 工作风格匹配要求
   - 团队规模匹配要求

请特别关注：
- 组织架构信息：理解岗位在组织中的位置和作用
- 部门文化：提取部门文化对候选人的要求
- 公司文化：提取公司文化对候选人的要求

输出JSON格式：
""")
        
        # JSON格式定义
        prompt_parts.append("""
{
  "requirements": {
    "education": {
      "degree": "本科",
      "major": ["计算机科学", "软件工程"]
    },
    "experience": {
      "years": 3,
      "fields": ["Web开发", "后端开发"]
    },
    "skills": ["Python", "Django", "PostgreSQL", "Redis"],
    "age": null,
    "location": null
  },
  "characteristics": {
    "core_responsibilities": ["负责核心业务系统开发", "参与技术架构设计"],
    "work_content": ["后端API开发", "数据库优化"],
    "development_prospects": "有机会参与大型项目，提升技术能力"
  },
  "preferences": {
    "reliability": "高",
    "innovation": "中",
    "teamwork": "高"
  },
  "organization_match_requirements": {
    "department_culture": "注重团队合作，追求技术创新",
    "work_style": "快节奏，注重效率",
    "team_size": "中等规模团队（10-20人）"
  }
}
""")
        
        return "\n".join(prompt_parts)

