"""
MongoDB 文档模型定义（用于类型提示和文档结构说明）
这些不是SQLAlchemy模型，而是用于说明MongoDB文档结构的类
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class JobProfileDocument(BaseModel):
    """岗位画像文档结构（MongoDB）"""
    _id: Optional[str] = None
    job_id: int
    parsed_data: Dict[str, Any] = Field(..., description="岗位解析数据")
    # parsed_data 结构示例：
    # {
    #   "title": "高级Python开发工程师",
    #   "requirements": {
    #     "education": {
    #       "degree": "本科及以上",
    #       "major": ["计算机科学", "软件工程"]
    #     },
    #     "experience": {
    #       "years": 3,
    #       "fields": ["Python", "Django", "PostgreSQL"]
    #     },
    #     "skills": ["Python", "Django", "PostgreSQL", "Redis"],
    #     "location": "北京",
    #     "salary_range": "20k-35k"
    #   },
    #   "description": "负责后端系统开发...",
    #   "preferences": {
    #     "reliability": "高",
    #     "security": "高"
    #   }
    # }
    parsed_at: datetime
    created_at: datetime
    updated_at: datetime


class ParsedResumeDocument(BaseModel):
    """简历解析结果文档结构（MongoDB，迁移现有数据）"""
    _id: Optional[str] = None
    parsed_resume_id: int  # PostgreSQL中的parsed_resume.id
    parsed_data: Dict[str, Any] = Field(..., description="简历解析数据（从PostgreSQL迁移）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime
    updated_at: datetime


class MatchDetailDocument(BaseModel):
    """匹配详情文档结构（MongoDB）"""
    _id: Optional[str] = None
    match_id: int  # PostgreSQL中的resume_job_match.id
    
    # 向量相似度结果
    vector_similarity: float = Field(..., description="向量相似度分数（0-1）")
    vector_details: Dict[str, Any] = Field(default_factory=dict, description="向量匹配详情")
    # vector_details 结构示例：
    # {
    #   "skill_similarity": 0.85,
    #   "experience_similarity": 0.78,
    #   "project_similarity": 0.82,
    #   "combined_similarity": 0.82
    # }
    
    # 规则匹配结果
    rule_match_result: Dict[str, Any] = Field(..., description="规则匹配结果")
    # rule_match_result 结构示例：
    # {
    #   "passed": true,
    #   "failed_rules": [],
    #   "rule_details": [
    #     {
    #       "rule_id": 1,
    #       "rule_name": "学历要求",
    #       "passed": true,
    #       "reason": "候选人学历为本科，满足要求"
    #     }
    #   ]
    # }
    
    # LLM深度分析结果
    llm_analysis: Dict[str, Any] = Field(..., description="LLM深度分析结果")
    # llm_analysis 结构示例：
    # {
    #   "score": 8.5,
    #   "strengths": [
    #     "具有丰富的Python开发经验",
    #     "熟悉Django框架"
    #   ],
    #   "weaknesses": [
    #     "缺少大型项目经验"
    #   ],
    #   "risk_points": [
    #     "跳槽频繁"
    #   ],
    #   "recommendation": "强烈推荐",
    #   "detailed_analysis": "候选人具有..."
    # }
    
    # 综合评分详情
    score_breakdown: Dict[str, Any] = Field(default_factory=dict, description="评分明细")
    # score_breakdown 结构示例：
    # {
    #   "vector_score": 8.2,  # 向量相似度转换后的分数
    #   "rule_score": 10.0,    # 规则匹配分数
    #   "llm_score": 8.5,      # LLM评分
    #   "final_score": 8.5,   # 最终综合分数
    #   "weights": {
    #     "vector": 0.3,
    #     "rule": 0.2,
    #     "llm": 0.5
    #   }
    # }
    
    created_at: datetime
    updated_at: datetime

