"""
MongoDB 服务层 - 提供文档操作的封装
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from ..core.config import settings

logger = logging.getLogger(__name__)


class MongoDBService:
    """MongoDB服务类，提供文档操作的封装"""
    
    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._db_override = db
    
    async def _ensure_connected(self):
        """确保MongoDB连接"""
        if self._db_override:
            self._db = self._db_override
            return
        
        if not self._client or not self._db:
            self._client = AsyncIOMotorClient(settings.mongodb_url)
            self._db = self._client.get_database()
            # 测试连接
            await self._db.command('ping')
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """获取数据库实例（延迟连接）"""
        if self._db_override:
            return self._db_override
        if not self._db:
            raise ConnectionError("MongoDB未连接，请先调用 _ensure_connected()")
        return self._db
    
    async def get_collection(self, name: str):
        """获取集合"""
        await self._ensure_connected()
        return self.db[name]
    
    # ========== 岗位画像文档操作 ==========
    
    async def save_job_profile(self, job_id: int, parsed_data: Dict[str, Any]) -> str:
        """保存岗位画像到MongoDB
        
        Args:
            job_id: 岗位ID（PostgreSQL）
            parsed_data: 岗位解析数据
        
        Returns:
            MongoDB文档ID
        """
        collection = await self.get_collection("job_profiles")
        now = datetime.utcnow()
        
        document = {
            "job_id": job_id,
            "parsed_data": parsed_data,
            "parsed_at": now,
            "created_at": now,
            "updated_at": now
        }
        
        result = await collection.insert_one(document)
        logger.info(f"岗位画像已保存: job_id={job_id}, mongodb_id={result.inserted_id}")
        return str(result.inserted_id)
    
    async def get_job_profile(self, job_id: int) -> Optional[Dict[str, Any]]:
        """获取岗位画像
        
        Args:
            job_id: 岗位ID
        
        Returns:
            岗位画像文档，如果不存在返回None
        """
        collection = await self.get_collection("job_profiles")
        document = await collection.find_one({"job_id": job_id})
        if document:
            document["_id"] = str(document["_id"])
        return document
    
    async def update_job_profile(self, job_id: int, parsed_data: Dict[str, Any]) -> bool:
        """更新岗位画像
        
        Args:
            job_id: 岗位ID
            parsed_data: 更新的解析数据
        
        Returns:
            是否更新成功
        """
        collection = await self.get_collection("job_profiles")
        result = await collection.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "parsed_data": parsed_data,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    # ========== 简历解析结果文档操作 ==========
    
    async def save_parsed_resume(self, parsed_resume_id: int, parsed_data: Dict[str, Any]) -> str:
        """保存简历解析结果到MongoDB（从PostgreSQL迁移）
        
        Args:
            parsed_resume_id: 解析结果ID（PostgreSQL）
            parsed_data: 解析数据
        
        Returns:
            MongoDB文档ID
        """
        collection = await self.get_collection("parsed_resumes")
        now = datetime.utcnow()
        
        document = {
            "parsed_resume_id": parsed_resume_id,
            "parsed_data": parsed_data,
            "metadata": {},
            "created_at": now,
            "updated_at": now
        }
        
        result = await collection.insert_one(document)
        logger.info(f"简历解析结果已保存: parsed_resume_id={parsed_resume_id}, mongodb_id={result.inserted_id}")
        return str(result.inserted_id)
    
    async def get_parsed_resume(self, parsed_resume_id: int) -> Optional[Dict[str, Any]]:
        """获取简历解析结果
        
        Args:
            parsed_resume_id: 解析结果ID
        
        Returns:
            解析结果文档，如果不存在返回None
        """
        collection = await self.get_collection("parsed_resumes")
        document = await collection.find_one({"parsed_resume_id": parsed_resume_id})
        if document:
            document["_id"] = str(document["_id"])
        return document
    
    # ========== 匹配详情文档操作 ==========
    
    async def save_match_detail(
        self,
        match_id: int,
        vector_similarity: float,
        rule_match_result: Dict[str, Any],
        llm_analysis: Dict[str, Any],
        score_breakdown: Optional[Dict[str, Any]] = None
    ) -> str:
        """保存匹配详情到MongoDB
        
        Args:
            match_id: 匹配ID（PostgreSQL）
            vector_similarity: 向量相似度
            rule_match_result: 规则匹配结果
            llm_analysis: LLM分析结果
            score_breakdown: 评分明细
        
        Returns:
            MongoDB文档ID
        """
        collection = await self.get_collection("match_details")
        now = datetime.utcnow()
        
        document = {
            "match_id": match_id,
            "vector_similarity": vector_similarity,
            "vector_details": {},
            "rule_match_result": rule_match_result,
            "llm_analysis": llm_analysis,
            "score_breakdown": score_breakdown or {},
            "created_at": now,
            "updated_at": now
        }
        
        result = await collection.insert_one(document)
        logger.info(f"匹配详情已保存: match_id={match_id}, mongodb_id={result.inserted_id}")
        return str(result.inserted_id)
    
    async def get_match_detail(self, match_id: int) -> Optional[Dict[str, Any]]:
        """获取匹配详情
        
        Args:
            match_id: 匹配ID
        
        Returns:
            匹配详情文档，如果不存在返回None
        """
        collection = await self.get_collection("match_details")
        document = await collection.find_one({"match_id": match_id})
        if document:
            document["_id"] = str(document["_id"])
        return document
    
    async def update_match_detail(
        self,
        match_id: int,
        vector_similarity: Optional[float] = None,
        rule_match_result: Optional[Dict[str, Any]] = None,
        llm_analysis: Optional[Dict[str, Any]] = None,
        score_breakdown: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新匹配详情
        
        Args:
            match_id: 匹配ID
            vector_similarity: 向量相似度（可选）
            rule_match_result: 规则匹配结果（可选）
            llm_analysis: LLM分析结果（可选）
            score_breakdown: 评分明细（可选）
        
        Returns:
            是否更新成功
        """
        collection = await self.get_collection("match_details")
        update_data = {"updated_at": datetime.utcnow()}
        
        if vector_similarity is not None:
            update_data["vector_similarity"] = vector_similarity
        if rule_match_result is not None:
            update_data["rule_match_result"] = rule_match_result
        if llm_analysis is not None:
            update_data["llm_analysis"] = llm_analysis
        if score_breakdown is not None:
            update_data["score_breakdown"] = score_breakdown
        
        result = await collection.update_one(
            {"match_id": match_id},
            {"$set": update_data}
        )
        return result.modified_count > 0


# 全局MongoDB服务实例
mongodb_service = MongoDBService()

