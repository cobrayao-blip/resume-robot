"""
岗位管理服务
"""
import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models.job import JobPosition, CompanyInfo
from ..services.llm_service import LLMService
from ..services.prompt_builder import PromptBuilder
from ..core.mongodb_service import mongodb_service
from pymilvus import Collection, DataType, FieldSchema, CollectionSchema, utility, connections
from ..core.config import settings
import numpy as np

logger = logging.getLogger(__name__)


class JobService:
    """岗位管理服务"""
    
    def __init__(self, db_session: Session, llm_service: Optional[LLMService] = None):
        self.db = db_session
        self.llm_service = llm_service or LLMService(db_session=db_session, provider="deepseek")
        self.prompt_builder = PromptBuilder(db_session)  # 新增PromptBuilder
    
    async def parse_job_profile(
        self,
        job_id: int,
        company_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        解析岗位画像
        
        Args:
            job_id: 岗位ID
            company_info: 公司信息（可选，用于增强Prompt）
        
        Returns:
            岗位画像数据
        """
        try:
            # 获取岗位信息
            job = self.db.query(JobPosition).filter(JobPosition.id == job_id).first()
            if not job:
                raise ValueError(f"岗位不存在: {job_id}")
            
            # 获取tenant_id（从job获取）
            tenant_id = job.tenant_id
            
            # 使用PromptBuilder构建岗位解析Prompt（整合组织架构信息）
            prompt = self.prompt_builder.build_job_parsing_prompt(
                job=job,
                tenant_id=tenant_id
            )
            
            # 调用LLM解析
            logger.info(f"开始解析岗位画像: job_id={job_id}, title={job.title}")
            parsed_data = await self.llm_service.chat_completion(
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # 解析JSON响应
            if isinstance(parsed_data, str):
                parsed_data = json.loads(parsed_data)
            
            # 保存到MongoDB
            mongodb_id = mongodb_service.save_job_profile(job_id, parsed_data)
            
            # 更新PostgreSQL中的mongodb_id
            job.mongodb_id = mongodb_id
            self.db.commit()
            
            logger.info(f"岗位画像解析完成: job_id={job_id}, mongodb_id={mongodb_id}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"解析岗位画像失败: job_id={job_id}, error={e}", exc_info=True)
            raise
    
    def _get_system_prompt(self) -> str:
        """获取系统Prompt"""
        return """你是资深的岗位分析专家。你的任务是根据岗位描述和要求，提取结构化的岗位画像信息。

核心任务：
1. **提取岗位要求**：从岗位描述中提取学历、经验、技能、年龄、地点等要求
2. **分析岗位特点**：识别岗位的核心职责、工作内容、发展前景
3. **提取偏好信息**：识别公司对候选人的偏好（如：可靠性、创新性、团队合作等）

重要约束：
- 所有信息必须基于提供的岗位描述，不能编造
- 如果信息不明确，使用null或空数组
- 输出标准的JSON格式
"""
    
    def _build_job_parsing_prompt(self, job: JobPosition, company_info: Optional[Dict[str, Any]] = None) -> str:
        """构建岗位解析Prompt"""
        prompt_parts = []
        
        # 公司信息（如果提供）
        if company_info:
            prompt_parts.append("## 公司信息")
            if company_info.get("name"):
                prompt_parts.append(f"公司名称: {company_info['name']}")
            if company_info.get("industry"):
                prompt_parts.append(f"行业: {company_info['industry']}")
            if company_info.get("products"):
                prompt_parts.append(f"产品/服务: {company_info['products']}")
            if company_info.get("application_scenarios"):
                prompt_parts.append(f"应用场景: {company_info['application_scenarios']}")
            if company_info.get("company_culture"):
                prompt_parts.append(f"公司文化: {company_info['company_culture']}")
            if company_info.get("preferences"):
                prompt_parts.append(f"偏好: {company_info['preferences']}")
            prompt_parts.append("")
        
        # 岗位信息
        prompt_parts.append("## 岗位信息")
        prompt_parts.append(f"岗位名称: {job.title}")
        if job.department:
            prompt_parts.append(f"部门: {job.department}")
        if job.description:
            prompt_parts.append(f"岗位描述:\n{job.description}")
        if job.requirements:
            prompt_parts.append(f"岗位要求:\n{job.requirements}")
        prompt_parts.append("")
        
        # 输出要求
        prompt_parts.append("## 输出要求")
        prompt_parts.append("请根据以上信息，提取结构化的岗位画像，输出JSON格式：")
        prompt_parts.append(json.dumps({
            "title": "岗位名称",
            "requirements": {
                "education": {
                    "degree": "学历要求（如：本科及以上、硕士等）",
                    "major": ["专业要求（数组）"]
                },
                "experience": {
                    "years": "工作经验年限（数字）",
                    "fields": ["相关领域（数组）"]
                },
                "skills": ["技能要求（数组）"],
                "age_range": "年龄要求（如：25-35岁）",
                "location": "工作地点",
                "salary_range": "薪资范围（如：20k-35k）"
            },
            "description": "岗位描述摘要",
            "preferences": {
                "reliability": "对可靠性的偏好（高/中/低）",
                "security": "对安全性的偏好（高/中/低）",
                "innovation": "对创新性的偏好（高/中/低）",
                "teamwork": "对团队合作的偏好（高/中/低）"
            }
        }, ensure_ascii=False, indent=2))
        
        return "\n".join(prompt_parts)
    
    async def vectorize_job(
        self,
        job_id: int,
        embedding_model: str = "deepseek"
    ) -> str:
        """
        将岗位向量化并存储到Milvus
        
        Args:
            job_id: 岗位ID
            embedding_model: 向量化模型（deepseek/qwen等）
        
        Returns:
            Milvus向量ID
        """
        try:
            # 获取岗位信息
            job = self.db.query(JobPosition).filter(JobPosition.id == job_id).first()
            if not job:
                raise ValueError(f"岗位不存在: {job_id}")
            
            # 获取岗位画像
            profile = mongodb_service.get_job_profile(job_id)
            if not profile:
                raise ValueError(f"岗位画像不存在，请先解析岗位画像: job_id={job_id}")
            
            parsed_data = profile.get("parsed_data", {})
            
            # 构建向量化文本
            vector_text = self._build_vector_text(job, parsed_data)
            
            # 生成向量（这里需要调用embedding API，暂时使用占位符）
            # TODO: 实现实际的embedding生成
            vector = await self._generate_embedding(vector_text, embedding_model)
            
            # 存储到Milvus
            vector_id = self._save_to_milvus(job_id, vector)
            
            # 更新PostgreSQL中的vector_id
            job.vector_id = vector_id
            self.db.commit()
            
            logger.info(f"岗位向量化完成: job_id={job_id}, vector_id={vector_id}")
            return vector_id
            
        except Exception as e:
            logger.error(f"岗位向量化失败: job_id={job_id}, error={e}", exc_info=True)
            raise
    
    def _build_vector_text(self, job: JobPosition, parsed_data: Dict[str, Any]) -> str:
        """构建用于向量化的文本"""
        parts = []
        
        # 岗位名称
        parts.append(f"岗位: {job.title}")
        
        # 岗位要求
        requirements = parsed_data.get("requirements", {})
        if requirements.get("skills"):
            parts.append(f"技能要求: {', '.join(requirements['skills'])}")
        if requirements.get("experience", {}).get("fields"):
            parts.append(f"相关领域: {', '.join(requirements['experience']['fields'])}")
        if requirements.get("education", {}).get("degree"):
            parts.append(f"学历要求: {requirements['education']['degree']}")
        
        # 岗位描述
        if parsed_data.get("description"):
            parts.append(f"岗位描述: {parsed_data['description']}")
        
        return " | ".join(parts)
    
    async def _generate_embedding(self, text: str, model: str = "deepseek") -> list:
        """
        生成文本向量
        
        TODO: 实现实际的embedding生成
        可以使用：
        1. DeepSeek Embedding API
        2. 千问 Embedding API
        3. sentence-transformers（本地）
        """
        # 占位符：返回768维的零向量
        # 实际实现时需要调用embedding API
        logger.warning(f"使用占位符向量，实际实现需要调用embedding API: model={model}")
        return [0.0] * 768
    
    def _save_to_milvus(self, job_id: int, vector: list) -> str:
        """保存向量到Milvus"""
        try:
            # 连接Milvus
            try:
                connections.connect(
                    alias="default",
                    host=settings.milvus_host,
                    port=settings.milvus_port
                )
            except Exception:
                pass  # 如果已连接则忽略
            
            collection_name = "job_vectors"
            
            # 检查集合是否存在
            if not utility.has_collection(collection_name):
                # 创建集合
                fields = [
                    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                    FieldSchema(name="job_id", dtype=DataType.INT64),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=len(vector)),
                    FieldSchema(name="vector_type", dtype=DataType.VARCHAR, max_length=50)
                ]
                schema = CollectionSchema(fields=fields, description="岗位向量集合")
                collection = Collection(name=collection_name, schema=schema)
                logger.info(f"创建Milvus集合: {collection_name}")
            else:
                collection = Collection(collection_name)
            
            # 插入数据
            data = [
                [job_id],
                [vector],
                ["combined"]
            ]
            result = collection.insert(data)
            collection.flush()
            
            # 返回插入的ID（这里简化处理，实际应该返回插入的ID）
            vector_id = str(result.primary_keys[0] if result.primary_keys else job_id)
            logger.info(f"向量已保存到Milvus: job_id={job_id}, vector_id={vector_id}")
            return vector_id
            
        except Exception as e:
            logger.error(f"保存向量到Milvus失败: {e}", exc_info=True)
            raise

