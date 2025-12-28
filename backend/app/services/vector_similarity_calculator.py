"""
向量相似度计算服务
统一向量生成和相似度计算
"""
import logging
import numpy as np
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from ..models.job import JobPosition
from ..core.config import settings

logger = logging.getLogger(__name__)


class VectorSimilarityCalculator:
    """向量相似度计算器"""
    
    def __init__(self, embedding_model: str = "deepseek"):
        self.embedding_model = embedding_model
        self.vector_dim = 768  # 根据模型调整（DeepSeek Embedding通常是768维）
    
    async def generate_resume_vector(
        self,
        resume_data: Dict[str, Any]
    ) -> List[float]:
        """
        生成简历向量
        
        提取关键信息：
        - 工作经历（公司、职位、职责）
        - 技能（技术栈、工具）
        - 教育背景（学校、专业、学历）
        - 项目经验（项目名称、职责、成果）
        
        Args:
            resume_data: 简历数据（从MongoDB或PostgreSQL获取）
        
        Returns:
            简历向量（768维）
        """
        try:
            # 构建向量化文本
            vector_text = self._build_resume_vector_text(resume_data)
            
            # 生成向量（调用Embedding API）
            vector = await self._generate_embedding(vector_text)
            
            return vector
            
        except Exception as e:
            logger.error(f"生成简历向量失败: {e}", exc_info=True)
            # 返回零向量作为fallback
            return [0.0] * self.vector_dim
    
    async def generate_job_vector(
        self,
        job: JobPosition,
        job_parsed_data: Optional[Dict[str, Any]] = None
    ) -> List[float]:
        """
        生成岗位向量
        
        提取关键信息：
        - 岗位要求（技能、经验、学历）
        - 岗位描述（职责、工作内容）
        - 部门信息（部门职责、部门特点）
        
        Args:
            job: 岗位对象
            job_parsed_data: 岗位画像数据（可选）
        
        Returns:
            岗位向量（768维）
        """
        try:
            # 构建向量化文本
            vector_text = self._build_job_vector_text(job, job_parsed_data)
            
            # 生成向量
            vector = await self._generate_embedding(vector_text)
            
            return vector
            
        except Exception as e:
            logger.error(f"生成岗位向量失败: {e}", exc_info=True)
            # 返回零向量作为fallback
            return [0.0] * self.vector_dim
    
    def calculate_similarity(
        self,
        vector1: List[float],
        vector2: List[float],
        method: str = "cosine"
    ) -> float:
        """
        计算向量相似度
        
        Args:
            vector1: 向量1
            vector2: 向量2
            method: 相似度计算方法（cosine/euclidean/dot_product）
        
        Returns:
            相似度分数（0-1）
        """
        try:
            v1 = np.array(vector1, dtype=np.float32)
            v2 = np.array(vector2, dtype=np.float32)
            
            # 确保向量维度一致
            if len(v1) != len(v2):
                logger.warning(f"向量维度不一致: {len(v1)} vs {len(v2)}")
                min_dim = min(len(v1), len(v2))
                v1 = v1[:min_dim]
                v2 = v2[:min_dim]
            
            if method == "cosine":
                # 余弦相似度
                dot_product = np.dot(v1, v2)
                norm1 = np.linalg.norm(v1)
                norm2 = np.linalg.norm(v2)
                
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                
                similarity = dot_product / (norm1 * norm2)
                # 余弦相似度范围是-1到1，但文本向量通常在0-1
                return max(0.0, float(similarity))
            
            elif method == "euclidean":
                # 欧氏距离（转换为相似度）
                distance = np.linalg.norm(v1 - v2)
                # 使用sigmoid函数将距离转换为相似度
                similarity = 1 / (1 + distance)
                return float(similarity)
            
            elif method == "dot_product":
                # 点积相似度（需要向量已归一化）
                return float(np.dot(v1, v2))
            
            else:
                raise ValueError(f"未知的相似度计算方法: {method}")
                
        except Exception as e:
            logger.error(f"计算向量相似度失败: {e}", exc_info=True)
            return 0.0
    
    def _build_resume_vector_text(self, resume_data: Dict[str, Any]) -> str:
        """
        构建简历向量化文本
        
        提取关键信息用于向量化
        """
        parts = []
        
        # 工作经历
        work_experiences = resume_data.get("work_experiences", [])
        for exp in work_experiences:
            company = exp.get("company", "")
            position = exp.get("position", "")
            if company or position:
                parts.append(f"工作: {company} {position}")
            
            responsibilities = exp.get("responsibilities", [])
            if responsibilities:
                parts.append(f"职责: {', '.join(responsibilities)}")
        
        # 技能
        skills = resume_data.get("skills", {})
        if isinstance(skills, dict):
            technical_skills = skills.get("technical", [])
            if technical_skills:
                parts.append(f"技能: {', '.join(technical_skills)}")
        elif isinstance(skills, list):
            parts.append(f"技能: {', '.join(skills)}")
        
        # 教育背景
        education = resume_data.get("education", [])
        for edu in education:
            school = edu.get("school", "")
            major = edu.get("major", "")
            degree = edu.get("degree", "")
            if school or major or degree:
                parts.append(f"教育: {school} {major} {degree}")
        
        # 项目经验
        projects = resume_data.get("projects", [])
        for proj in projects:
            name = proj.get("name", "")
            description = proj.get("description", "")
            if name or description:
                parts.append(f"项目: {name} {description}")
        
        return " | ".join(parts)
    
    def _build_job_vector_text(
        self,
        job: JobPosition,
        job_parsed_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建岗位向量化文本
        
        提取关键信息用于向量化
        """
        parts = []
        
        # 岗位名称
        if job.title:
            parts.append(f"岗位: {job.title}")
        
        # 岗位要求（从岗位画像中提取）
        if job_parsed_data:
            requirements = job_parsed_data.get("requirements", {})
            if isinstance(requirements, dict):
                # 技能要求
                skills = requirements.get("skills", [])
                if skills:
                    parts.append(f"技能要求: {', '.join(skills)}")
                
                # 相关领域
                experience = requirements.get("experience", {})
                if isinstance(experience, dict):
                    fields = experience.get("fields", [])
                    if fields:
                        parts.append(f"相关领域: {', '.join(fields)}")
        
        # 岗位描述
        if job.description:
            parts.append(f"岗位描述: {job.description}")
        
        # 岗位要求（原始文本）
        if job.requirements:
            parts.append(f"岗位要求: {job.requirements}")
        
        # 部门信息（如果有关联）
        if job.department_obj:
            parts.append(f"部门: {job.department_obj.name}")
            if job.department_obj.description:
                parts.append(f"部门职责: {job.department_obj.description}")
        
        return " | ".join(parts)
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        生成文本向量
        
        TODO: 实现实际的embedding生成
        可以使用：
        1. DeepSeek Embedding API
        2. 千问 Embedding API
        3. sentence-transformers（本地）
        
        当前返回占位符向量
        """
        # 占位符：返回768维的零向量
        # 实际实现时需要调用embedding API
        logger.warning(f"使用占位符向量，实际实现需要调用embedding API: model={self.embedding_model}")
        return [0.0] * self.vector_dim
    
    def normalize_vector(self, vector: List[float]) -> List[float]:
        """
        归一化向量（L2归一化）
        
        Args:
            vector: 原始向量
        
        Returns:
            归一化后的向量
        """
        try:
            v = np.array(vector, dtype=np.float32)
            norm = np.linalg.norm(v)
            
            if norm == 0:
                return vector
            
            normalized = v / norm
            return normalized.tolist()
            
        except Exception as e:
            logger.error(f"归一化向量失败: {e}", exc_info=True)
            return vector

