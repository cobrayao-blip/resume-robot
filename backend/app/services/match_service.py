"""
简历匹配服务
"""
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from ..models.job import JobPosition, ResumeJobMatch, MatchModel, CompanyInfo
from ..models.resume import ParsedResume, CandidateResume
from ..services.filter_service import FilterService
from ..services.llm_service import LLMService
from ..services.prompt_builder import PromptBuilder
from ..services.match_score_fusion import MatchScoreFusion
from ..core.mongodb_service import mongodb_service
from pymilvus import Collection, DataType, FieldSchema, CollectionSchema, utility, connections
from ..core.config import settings
import numpy as np

logger = logging.getLogger(__name__)


class MatchService:
    """简历匹配服务"""
    
    def __init__(self, db_session: Session, llm_service: Optional[LLMService] = None):
        self.db = db_session
        self.llm_service = llm_service or LLMService(db_session=db_session, provider="deepseek")
        self.filter_service = FilterService(db_session=db_session)
        self.prompt_builder = PromptBuilder(db_session)  # 新增PromptBuilder
        self.vector_calculator = VectorSimilarityCalculator(embedding_model="deepseek")  # 新增向量计算器
    
    async def match_resume_to_job(
        self,
        resume_id: int,
        job_id: int,
        resume_type: str = "parsed",
        match_model_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        匹配简历与岗位
        
        Args:
            resume_id: 简历ID
            job_id: 岗位ID
            resume_type: 简历类型（parsed/candidate）
            match_model_id: 匹配模型ID（如果为None，使用默认模型）
        
        Returns:
            匹配结果
        """
        try:
            # 获取岗位信息
            job = self.db.query(JobPosition).filter(JobPosition.id == job_id).first()
            if not job:
                raise ValueError(f"岗位不存在: {job_id}")
            
            # 获取简历数据
            resume_data = self._get_resume_data(resume_id, resume_type)
            if not resume_data:
                raise ValueError(f"简历不存在: {resume_id}")
            
            # 获取匹配模型
            match_model = self._get_match_model(match_model_id)
            
            # 1. 向量相似度匹配
            vector_similarity = await self._calculate_vector_similarity(resume_id, job_id, resume_type)
            
            # 2. 规则匹配（使用预筛选规则）
            rule_match_result = self.filter_service.execute_filter_rules(
                resume_data=resume_data,
                all_rules=True
            )
            
            # 3. LLM深度匹配
            llm_analysis = await self._llm_deep_match(resume_data, job, match_model)
            
            # 4. 提取组织匹配度（从LLM分析结果中）
            fusion_service = MatchScoreFusion(match_model=match_model)
            org_match_score = fusion_service.extract_org_match_score(llm_analysis)
            
            # 5. 综合评分（使用新的融合算法）
            final_score, score_breakdown = fusion_service.calculate_final_score(
                vector_similarity=vector_similarity,
                rule_match_result=rule_match_result,
                llm_analysis=llm_analysis,
                org_match_score=org_match_score,
                job=job
            )
            
            # 5. 生成匹配标签
            match_label = self._generate_match_label(final_score, match_model)
            
            # 6. 保存匹配结果到PostgreSQL
            match_record = self._save_match_record(
                resume_id=resume_id,
                job_id=job_id,
                match_score=final_score,
                match_label=match_label,
                resume_type=resume_type
            )
            
            # 7. 保存匹配详情到MongoDB
            match_detail = {
                "vector_similarity": vector_similarity,
                "vector_details": {},
                "rule_match_result": rule_match_result,
                "llm_analysis": llm_analysis,
                "score_breakdown": score_breakdown
            }
            mongodb_detail_id = mongodb_service.save_match_detail(
                match_id=match_record.id,
                vector_similarity=vector_similarity,
                rule_match_result=rule_match_result,
                llm_analysis=llm_analysis,
                score_breakdown=score_breakdown
            )
            
            # 更新PostgreSQL中的mongodb_detail_id
            match_record.mongodb_detail_id = mongodb_detail_id
            self.db.commit()
            
            logger.info(f"简历匹配完成: resume_id={resume_id}, job_id={job_id}, score={final_score}, label={match_label}")
            
            return {
                "match_id": match_record.id,
                "resume_id": resume_id,
                "job_id": job_id,
                "match_score": final_score,
                "match_label": match_label,
                "vector_similarity": vector_similarity,
                "rule_match_result": rule_match_result,
                "llm_analysis": llm_analysis,
                "score_breakdown": score_breakdown
            }
            
        except Exception as e:
            logger.error(f"简历匹配失败: resume_id={resume_id}, job_id={job_id}, error={e}", exc_info=True)
            raise
    
    def _get_resume_data(self, resume_id: int, resume_type: str) -> Optional[Dict[str, Any]]:
        """获取简历数据"""
        try:
            if resume_type == "parsed":
                parsed_resume = self.db.query(ParsedResume).filter(ParsedResume.id == resume_id).first()
                if not parsed_resume:
                    return None
                
                # 优先从MongoDB获取
                resume_doc = mongodb_service.get_parsed_resume(resume_id)
                if resume_doc:
                    return resume_doc.get("parsed_data", {})
                else:
                    return parsed_resume.parsed_data
            else:
                candidate_resume = self.db.query(CandidateResume).filter(CandidateResume.id == resume_id).first()
                if not candidate_resume:
                    return None
                return candidate_resume.resume_data
        except Exception as e:
            logger.error(f"获取简历数据失败: {e}", exc_info=True)
            return None
    
    def _get_match_model(self, model_id: Optional[int] = None) -> Optional[MatchModel]:
        """获取匹配模型"""
        if model_id:
            return self.db.query(MatchModel).filter(MatchModel.id == model_id).first()
        else:
            # 获取默认模型
            return self.db.query(MatchModel).filter(
                MatchModel.is_default == True,
                MatchModel.is_active == True
            ).first()
    
    async def _calculate_vector_similarity(
        self,
        resume_id: int,
        job_id: int,
        resume_type: str
    ) -> float:
        """
        计算向量相似度
        
        Returns:
            相似度分数（0-1）
        """
        try:
            # 获取岗位向量
            job = self.db.query(JobPosition).filter(JobPosition.id == job_id).first()
            if not job or not job.vector_id:
                logger.warning(f"岗位未向量化: job_id={job_id}")
                return 0.0
            
            # 获取简历向量（需要先向量化）
            resume_vector_id = await self._ensure_resume_vectorized(resume_id, resume_type)
            if not resume_vector_id:
                logger.warning(f"简历未向量化: resume_id={resume_id}")
                return 0.0
            
            # 从Milvus检索相似度
            similarity = await self._search_vector_similarity(resume_vector_id, job.vector_id)
            
            return similarity
            
        except Exception as e:
            logger.error(f"计算向量相似度失败: {e}", exc_info=True)
            return 0.0
    
    async def _ensure_resume_vectorized(self, resume_id: int, resume_type: str) -> Optional[str]:
        """确保简历已向量化"""
        try:
            # 检查是否已向量化（这里简化处理，实际应该存储vector_id）
            # TODO: 在ParsedResume或CandidateResume表中添加vector_id字段
            
            # 如果未向量化，进行向量化
            # TODO: 实现简历向量化逻辑
            return None
        except Exception as e:
            logger.error(f"确保简历向量化失败: {e}", exc_info=True)
            return None
    
    async def _search_vector_similarity(self, resume_vector_id: str, job_vector_id: str) -> float:
        """从Milvus检索向量相似度"""
        try:
            # 连接Milvus
            try:
                connections.connect(
                    alias="default",
                    host=settings.milvus_host,
                    port=settings.milvus_port
                )
            except Exception:
                pass
            
            collection_name = "resume_vectors"
            if not utility.has_collection(collection_name):
                logger.warning(f"Milvus集合不存在: {collection_name}")
                return 0.0
            
            collection = Collection(collection_name)
            collection.load()
            
            # 获取岗位向量
            # TODO: 实现实际的向量检索
            # 这里使用占位符
            return 0.5
            
        except Exception as e:
            logger.error(f"检索向量相似度失败: {e}", exc_info=True)
            return 0.0
    
    async def _llm_deep_match(
        self,
        resume_data: Dict[str, Any],
        job: JobPosition,
        match_model: Optional[MatchModel]
    ) -> Dict[str, Any]:
        """
        使用LLM进行深度匹配分析
        
        Returns:
            LLM分析结果
        """
        try:
            # 获取岗位画像
            job_profile = mongodb_service.get_job_profile(job.id)
            if not job_profile:
                return {
                    "score": 0.0,
                    "strengths": [],
                    "weaknesses": [],
                    "risk_points": [],
                    "recommendation": "无法分析",
                    "detailed_analysis": "岗位画像不存在"
                }
            
            job_parsed_data = job_profile.get("parsed_data", {})
            
            # 获取tenant_id（从job获取）
            tenant_id = job.tenant_id
            
            # 使用PromptBuilder构建匹配分析Prompt（整合组织架构信息）
            prompt = self.prompt_builder.build_match_analysis_prompt(
                resume_data=resume_data,
                job=job,
                job_parsed_data=job_parsed_data,
                tenant_id=tenant_id
            )
            
            # 调用LLM分析
            analysis_result = await self.llm_service.chat_completion(
                messages=[
                    {"role": "system", "content": self._get_match_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # 解析JSON响应
            if isinstance(analysis_result, str):
                analysis_result = json.loads(analysis_result)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"LLM深度匹配失败: {e}", exc_info=True)
            return {
                "score": 0.0,
                "strengths": [],
                "weaknesses": [],
                "risk_points": [],
                "recommendation": "分析失败",
                "detailed_analysis": f"LLM分析异常: {str(e)}"
            }
    
    def _get_match_system_prompt(self) -> str:
        """获取匹配分析系统Prompt"""
        return """你是资深的HR招聘专家。你的任务是根据候选人的简历和岗位要求，进行深度匹配分析。

核心任务：
1. **匹配度评分**：给出0-10分的匹配度评分
2. **优势分析**：列出候选人的优势（与岗位要求匹配的点）
3. **劣势分析**：列出候选人的劣势（不符合岗位要求的点）
4. **风险点识别**：识别可能的风险点（如：跳槽频繁、技能不匹配等）
5. **推荐建议**：给出推荐建议（强烈推荐/推荐/谨慎推荐/不推荐）

重要约束：
- 评分要客观、准确
- 所有分析必须基于提供的简历和岗位信息
- 不能编造信息
- 输出标准的JSON格式
"""
    
    def _build_match_analysis_prompt(
        self,
        resume_data: Dict[str, Any],
        job: JobPosition,
        job_parsed_data: Dict[str, Any],
        company_info: Optional[CompanyInfo]
    ) -> str:
        """构建匹配分析Prompt"""
        prompt_parts = []
        
        # 公司信息
        if company_info:
            prompt_parts.append("## 公司信息")
            if company_info.name:
                prompt_parts.append(f"公司名称: {company_info.name}")
            if company_info.industry:
                prompt_parts.append(f"行业: {company_info.industry}")
            if company_info.preferences:
                prompt_parts.append(f"偏好: {company_info.preferences}")
            prompt_parts.append("")
        
        # 岗位信息
        prompt_parts.append("## 岗位信息")
        prompt_parts.append(f"岗位名称: {job.title}")
        if job.department:
            prompt_parts.append(f"部门: {job.department}")
        if job.description:
            prompt_parts.append(f"岗位描述: {job.description}")
        if job.requirements:
            prompt_parts.append(f"岗位要求: {job.requirements}")
        
        # 岗位画像
        if job_parsed_data:
            prompt_parts.append("\n## 岗位画像（结构化）")
            prompt_parts.append(json.dumps(job_parsed_data, ensure_ascii=False, indent=2))
        
        prompt_parts.append("\n## 候选人简历")
        prompt_parts.append(json.dumps(resume_data, ensure_ascii=False, indent=2))
        
        prompt_parts.append("\n## 分析要求")
        prompt_parts.append("请根据以上信息，进行深度匹配分析，输出JSON格式：")
        prompt_parts.append(json.dumps({
            "score": "匹配度分数（0-10，浮点数）",
            "strengths": ["优势1", "优势2"],
            "weaknesses": ["劣势1", "劣势2"],
            "risk_points": ["风险点1", "风险点2"],
            "recommendation": "推荐建议（强烈推荐/推荐/谨慎推荐/不推荐）",
            "detailed_analysis": "详细分析说明"
        }, ensure_ascii=False, indent=2))
        
        return "\n".join(prompt_parts)
    
    def _calculate_final_score(
        self,
        vector_similarity: float,
        rule_match_result: Dict[str, Any],
        llm_analysis: Dict[str, Any],
        match_model: Optional[MatchModel]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        计算最终匹配分数
        
        Returns:
            (最终分数, 评分明细)
        """
        try:
            # 获取模型配置（默认权重）
            if match_model:
                config = match_model.model_config
            else:
                config = {
                    "vector_weight": 0.3,
                    "rule_weight": 0.2,
                    "llm_weight": 0.5
                }
            
            vector_weight = config.get("vector_weight", 0.3)
            rule_weight = config.get("rule_weight", 0.2)
            llm_weight = config.get("llm_weight", 0.5)
            
            # 1. 向量相似度分数（0-1转换为0-10）
            vector_score = vector_similarity * 10.0
            
            # 2. 规则匹配分数（0-10）
            if rule_match_result.get("passed"):
                rule_score = 10.0
            else:
                # 根据失败规则数量计算分数
                total_rules = len(rule_match_result.get("rule_details", []))
                failed_rules = len(rule_match_result.get("failed_rules", []))
                if total_rules > 0:
                    rule_score = (total_rules - failed_rules) / total_rules * 10.0
                else:
                    rule_score = 10.0
            
            # 3. LLM评分（0-10）
            llm_score = float(llm_analysis.get("score", 0.0))
            
            # 4. 加权综合
            final_score = (
                vector_score * vector_weight +
                rule_score * rule_weight +
                llm_score * llm_weight
            )
            
            # 确保分数在0-10范围内
            final_score = max(0.0, min(10.0, final_score))
            
            score_breakdown = {
                "vector_score": round(vector_score, 2),
                "rule_score": round(rule_score, 2),
                "llm_score": round(llm_score, 2),
                "final_score": round(final_score, 2),
                "weights": {
                    "vector": vector_weight,
                    "rule": rule_weight,
                    "llm": llm_weight
                },
                "calculation": f"{vector_score:.2f} * {vector_weight} + {rule_score:.2f} * {rule_weight} + {llm_score:.2f} * {llm_weight} = {final_score:.2f}"
            }
            
            return final_score, score_breakdown
            
        except Exception as e:
            logger.error(f"计算最终分数失败: {e}", exc_info=True)
            return 0.0, {}
    
    def _generate_match_label(
        self,
        final_score: float,
        match_model: Optional[MatchModel]
    ) -> str:
        """生成匹配标签"""
        try:
            # 获取阈值配置
            if match_model:
                thresholds = match_model.model_config.get("thresholds", {})
            else:
                thresholds = {
                    "strongly_recommended": 8.0,
                    "recommended": 6.0,
                    "cautious": 4.0
                }
            
            strongly_recommended = thresholds.get("strongly_recommended", 8.0)
            recommended = thresholds.get("recommended", 6.0)
            cautious = thresholds.get("cautious", 4.0)
            
            if final_score >= strongly_recommended:
                return "强烈推荐"
            elif final_score >= recommended:
                return "推荐"
            elif final_score >= cautious:
                return "谨慎推荐"
            else:
                return "不推荐"
                
        except Exception as e:
            logger.error(f"生成匹配标签失败: {e}", exc_info=True)
            return "不推荐"
    
    def _save_match_record(
        self,
        resume_id: int,
        job_id: int,
        match_score: float,
        match_label: str,
        resume_type: str
    ) -> ResumeJobMatch:
        """保存匹配记录到PostgreSQL"""
        try:
            # 检查是否已存在匹配记录
            existing = self.db.query(ResumeJobMatch).filter(
                ResumeJobMatch.resume_id == resume_id,
                ResumeJobMatch.job_id == job_id
            ).first()
            
            if existing:
                # 更新现有记录
                existing.match_score = match_score
                existing.match_label = match_label
                existing.status = "pending"
                self.db.commit()
                self.db.refresh(existing)
                return existing
            else:
                # 创建新记录
                # 注意：这里需要根据resume_type确定正确的resume_id
                # 如果是parsed_resume，需要找到对应的candidate_resume_id
                # 简化处理：直接使用resume_id
                match_record = ResumeJobMatch(
                    resume_id=resume_id,
                    job_id=job_id,
                    match_score=match_score,
                    match_label=match_label,
                    status="pending"
                )
                self.db.add(match_record)
                self.db.commit()
                self.db.refresh(match_record)
                return match_record
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"保存匹配记录失败: {e}", exc_info=True)
            raise

