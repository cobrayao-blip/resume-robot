"""
批量操作服务
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models.job import JobPosition, ResumeJobMatch
from ..models.resume import ParsedResume, CandidateResume
from ..services.resume_parser import ResumeParser
from ..services.llm_service import LLMService
from ..services.match_service import MatchService
from ..services.filter_service import FilterService
from ..core.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)


class BatchService:
    """批量操作服务"""
    
    def __init__(self, db_session: Session, llm_service: Optional[LLMService] = None):
        self.db = db_session
        self.llm_service = llm_service or LLMService(db_session=db_session, provider="deepseek")
        self.match_service = MatchService(db_session=db_session, llm_service=self.llm_service)
        self.filter_service = FilterService(db_session=db_session)
        self.resume_parser = ResumeParser()
    
    async def batch_upload_and_parse(
        self,
        files: List[Any],
        user_id: int,
        job_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        批量上传并解析简历
        
        Args:
            files: 文件列表
            user_id: 用户ID
            job_id: 岗位ID（可选，如果提供则直接关联到岗位）
        
        Returns:
            批量处理结果
        """
        results = []
        success_count = 0
        failed_count = 0
        
        for file in files:
            try:
                # 解析单个文件
                result = await self._parse_single_file(file, user_id, job_id)
                results.append({
                    "file_name": file.filename,
                    "success": True,
                    "data": result
                })
                success_count += 1
                
            except Exception as e:
                logger.error(f"批量上传解析失败: file={file.filename}, error={e}", exc_info=True)
                results.append({
                    "file_name": file.filename,
                    "success": False,
                    "error": str(e)
                })
                failed_count += 1
        
        return {
            "total": len(files),
            "success": success_count,
            "failed": failed_count,
            "results": results
        }
    
    async def _parse_single_file(
        self,
        file: Any,
        user_id: int,
        job_id: Optional[int]
    ) -> Dict[str, Any]:
        """解析单个文件"""
        import hashlib
        import tempfile
        import os
        
        tmp_file_path = None
        try:
            # 1. 保存临时文件
            file_content = await file.read()
            file_ext = file.filename.split(".")[-1] if "." in file.filename else ""
            file_type = "pdf" if file_ext.lower() == "pdf" else "docx"
            
            # 计算文件hash
            file_hash = hashlib.md5(file_content).hexdigest()
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp_file:
                tmp_file.write(file_content)
                tmp_file_path = tmp_file.name
            
            # 2. 提取文本
            raw_text = self.resume_parser._extract_text(tmp_file_path, file_type)
            
            # 3. 解析简历
            parsed_data = await self.llm_service.parse_resume_text_v2(
                raw_text=raw_text,
                user=None,
                db_session=self.db
            )
            
            # 4. 保存解析结果
            
            # 检查是否已存在
            existing = self.db.query(ParsedResume).filter(
                ParsedResume.file_hash == file_hash
            ).first()
            
            if existing:
                parsed_resume_id = existing.id
                logger.info(f"简历已存在，使用现有解析结果: parsed_resume_id={parsed_resume_id}")
            else:
                # 创建解析结果
                parsed_resume = ParsedResume(
                    user_id=user_id,
                    name=f"{file.filename}解析结果",
                    parsed_data=parsed_data,
                    raw_text=raw_text,
                    candidate_name=parsed_data.get("basic_info", {}).get("name"),
                    source_file_name=file.filename,
                    source_file_type=file.filename.split(".")[-1] if "." in file.filename else "",
                    file_hash=file_hash
                )
                self.db.add(parsed_resume)
                self.db.commit()
                self.db.refresh(parsed_resume)
                parsed_resume_id = parsed_resume.id
                
                # 保存到MongoDB
                await mongodb_service.save_parsed_resume(parsed_resume_id, parsed_data)
            
            # 5. 如果指定了岗位，执行预筛选
            filter_result = None
            if job_id:
                resume_data = parsed_data
                filter_result = await self.filter_service.execute_filter_rules(
                    resume_id=parsed_resume_id,
                    resume_type="parsed_resume",
                    all_rules=True
                )
            
            return {
                "parsed_resume_id": parsed_resume_id,
                "candidate_name": parsed_data.get("basic_info", {}).get("name"),
                "filter_result": filter_result
            }
        finally:
            # 清理临时文件
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
    
    async def batch_match_resumes_to_job(
        self,
        resume_ids: List[int],
        job_id: int,
        resume_type: str = "parsed",
        match_model_id: Optional[int] = None,
        auto_filter: bool = True
    ) -> Dict[str, Any]:
        """
        批量匹配简历与岗位
        
        Args:
            resume_ids: 简历ID列表
            job_id: 岗位ID
            resume_type: 简历类型
            match_model_id: 匹配模型ID
            auto_filter: 是否自动执行预筛选（只匹配通过预筛选的简历）
        
        Returns:
            批量匹配结果
        """
        results = []
        success_count = 0
        failed_count = 0
        
        # 如果启用自动筛选，先执行预筛选
        if auto_filter:
            filtered_resume_ids = []
            for resume_id in resume_ids:
                try:
                    resume_data = self.match_service._get_resume_data(resume_id, resume_type)
                    if resume_data:
                        filter_result = self.filter_service.execute_filter_rules(
                            resume_data=resume_data,
                            all_rules=True
                        )
                        if filter_result.get("passed"):
                            filtered_resume_ids.append(resume_id)
                except Exception as e:
                    logger.warning(f"预筛选失败，跳过: resume_id={resume_id}, error={e}")
            
            resume_ids = filtered_resume_ids
            logger.info(f"预筛选后剩余简历数: {len(resume_ids)}")
        
        # 批量匹配
        for resume_id in resume_ids:
            try:
                result = await self.match_service.match_resume_to_job(
                    resume_id=resume_id,
                    job_id=job_id,
                    resume_type=resume_type,
                    match_model_id=match_model_id
                )
                results.append({
                    "resume_id": resume_id,
                    "success": True,
                    "data": result
                })
                success_count += 1
                
            except Exception as e:
                logger.error(f"批量匹配失败: resume_id={resume_id}, job_id={job_id}, error={e}", exc_info=True)
                results.append({
                    "resume_id": resume_id,
                    "success": False,
                    "error": str(e)
                })
                failed_count += 1
        
        # 统计结果
        strongly_recommended = sum(1 for r in results if r.get("success") and r.get("data", {}).get("match_label") == "强烈推荐")
        recommended = sum(1 for r in results if r.get("success") and r.get("data", {}).get("match_label") == "推荐")
        cautious = sum(1 for r in results if r.get("success") and r.get("data", {}).get("match_label") == "谨慎推荐")
        not_recommended = sum(1 for r in results if r.get("success") and r.get("data", {}).get("match_label") == "不推荐")
        
        return {
            "total": len(resume_ids),
            "success": success_count,
            "failed": failed_count,
            "summary": {
                "strongly_recommended": strongly_recommended,
                "recommended": recommended,
                "cautious": cautious,
                "not_recommended": not_recommended
            },
            "results": results
        }
    
    async def batch_generate_reports(
        self,
        match_ids: List[int],
        template_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        批量生成推荐报告
        
        Args:
            match_ids: 匹配记录ID列表
            template_id: 模板ID
            user_id: 用户ID
        
        Returns:
            批量生成结果
        """
        results = []
        success_count = 0
        failed_count = 0
        
        for match_id in match_ids:
            try:
                # 获取匹配记录
                match = self.db.query(ResumeJobMatch).filter(ResumeJobMatch.id == match_id).first()
                if not match:
                    results.append({
                        "match_id": match_id,
                        "success": False,
                        "error": "匹配记录不存在"
                    })
                    failed_count += 1
                    continue
                
                # 获取简历数据
                resume = self.db.query(CandidateResume).filter(CandidateResume.id == match.resume_id).first()
                if not resume:
                    # 尝试从parsed_resume获取
                    parsed_resume = self.db.query(ParsedResume).filter(ParsedResume.id == match.resume_id).first()
                    if not parsed_resume:
                        results.append({
                            "match_id": match_id,
                            "success": False,
                            "error": "简历不存在"
                        })
                        failed_count += 1
                        continue
                    
                    # 从parsed_resume创建candidate_resume
                    resume_data = parsed_resume.parsed_data
                    candidate_resume = CandidateResume(
                        user_id=user_id,
                        parsed_resume_id=parsed_resume.id,
                        template_id=template_id,
                        resume_data=resume_data,
                        candidate_name=parsed_resume.candidate_name,
                        title=f"{parsed_resume.candidate_name}的推荐报告",
                        source_file_name=parsed_resume.source_file_name,
                        source_file_type=parsed_resume.source_file_type,
                        source_file_path=parsed_resume.source_file_path
                    )
                    self.db.add(candidate_resume)
                    self.db.commit()
                    self.db.refresh(candidate_resume)
                    resume = candidate_resume
                
                # 获取匹配详情
                match_detail = mongodb_service.get_match_detail(match_id)
                
                # 生成报告数据（包含匹配分析）
                report_data = self._build_report_data(resume, match, match_detail)
                
                # 更新简历数据（添加匹配分析）
                resume.resume_data = report_data
                self.db.commit()
                
                results.append({
                    "match_id": match_id,
                    "resume_id": resume.id,
                    "success": True,
                    "data": {
                        "resume_id": resume.id,
                        "candidate_name": resume.candidate_name,
                        "match_score": match.match_score,
                        "match_label": match.match_label
                    }
                })
                success_count += 1
                
            except Exception as e:
                logger.error(f"批量生成报告失败: match_id={match_id}, error={e}", exc_info=True)
                results.append({
                    "match_id": match_id,
                    "success": False,
                    "error": str(e)
                })
                failed_count += 1
        
        return {
            "total": len(match_ids),
            "success": success_count,
            "failed": failed_count,
            "results": results
        }
    
    def _build_report_data(
        self,
        resume: CandidateResume,
        match: ResumeJobMatch,
        match_detail: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """构建报告数据（包含匹配分析）"""
        report_data = resume.resume_data.copy() if isinstance(resume.resume_data, dict) else {}
        
        # 添加匹配分析信息
        if match_detail:
            llm_analysis = match_detail.get("llm_analysis", {})
            report_data["match_analysis"] = {
                "match_score": match.match_score,
                "match_label": match.match_label,
                "strengths": llm_analysis.get("strengths", []),
                "weaknesses": llm_analysis.get("weaknesses", []),
                "risk_points": llm_analysis.get("risk_points", []),
                "recommendation": llm_analysis.get("recommendation", ""),
                "detailed_analysis": llm_analysis.get("detailed_analysis", "")
            }
        
        return report_data

