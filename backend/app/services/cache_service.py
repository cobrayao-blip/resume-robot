"""
解析结果缓存服务
使用Redis存储解析结果，基于文件内容hash作为key
"""
import hashlib
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool
from ..core.config import settings
from ..core.constants import REDIS_MAX_CONNECTIONS, CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)

class CacheService:
    """缓存服务类"""
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.connection_pool: Optional[ConnectionPool] = None
        self.cache_prefix = "resume_parse:"
        self.cache_ttl = CACHE_TTL_SECONDS  # 使用常量配置
        
    async def connect(self):
        """连接Redis（使用连接池）"""
        if self.redis_client is None:
            try:
                # 创建连接池
                self.connection_pool = ConnectionPool.from_url(
                    settings.redis_url,
                    max_connections=REDIS_MAX_CONNECTIONS,
                    encoding="utf-8",
                    decode_responses=True
                )
                # 从连接池创建Redis客户端
                self.redis_client = aioredis.Redis(connection_pool=self.connection_pool)
                logger.info("Redis连接池创建成功")
            except Exception as e:
                logger.warning(f"Redis连接失败，将使用内存缓存: {e}")
                self.redis_client = None
                self.connection_pool = None
    
    async def close(self):
        """关闭Redis连接和连接池"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
        if self.connection_pool:
            await self.connection_pool.disconnect()
            self.connection_pool = None
    
    def _get_file_hash(self, file_content: bytes) -> str:
        """计算文件内容的MD5 hash"""
        return hashlib.md5(file_content).hexdigest()
    
    def _get_cache_key(self, file_hash: str) -> str:
        """生成缓存key"""
        return f"{self.cache_prefix}{file_hash}"
    
    async def get_cached_result(self, file_content: bytes) -> Optional[Dict[str, Any]]:
        """
        获取缓存的解析结果
        返回: 解析结果字典，如果不存在则返回None
        """
        try:
            await self.connect()
            if self.redis_client is None:
                return None
            
            file_hash = self._get_file_hash(file_content)
            cache_key = self._get_cache_key(file_hash)
            
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                logger.info(f"缓存命中: {file_hash[:8]}...")
                return json.loads(cached_data)
            
            logger.debug(f"缓存未命中: {file_hash[:8]}...")
            return None
            
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")
            return None
    
    async def set_cached_result(self, file_content: bytes, parse_result: Dict[str, Any]) -> bool:
        """
        设置缓存结果
        返回: 是否成功
        """
        try:
            file_hash = self._get_file_hash(file_content)
            return await self.set_cached_result_by_hash(file_hash, parse_result)
        except Exception as e:
            logger.warning(f"设置缓存失败: {e}")
            return False
    
    async def set_cached_result_by_hash(self, file_hash: str, parse_result: Dict[str, Any]) -> bool:
        """
        根据文件hash设置缓存结果
        返回: 是否成功
        """
        try:
            await self.connect()
            if self.redis_client is None:
                return False
            
            cache_key = self._get_cache_key(file_hash)
            
            # 序列化结果
            cached_data = json.dumps(parse_result, ensure_ascii=False)
            
            # 设置缓存，带过期时间
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                cached_data
            )
            
            logger.info(f"缓存已设置: {file_hash[:8]}... (TTL: {self.cache_ttl}秒)")
            return True
            
        except Exception as e:
            logger.warning(f"设置缓存失败: {e}")
            return False
    
    async def delete_cache(self, file_content: bytes) -> bool:
        """
        删除缓存
        返回: 是否成功
        """
        try:
            await self.connect()
            if self.redis_client is None:
                return False
            
            file_hash = self._get_file_hash(file_content)
            return await self.delete_cache_by_hash(file_hash)
            
        except Exception as e:
            logger.warning(f"删除缓存失败: {e}")
            return False
    
    async def delete_cache_by_hash(self, file_hash: str) -> bool:
        """
        根据文件hash删除缓存
        返回: 是否成功
        """
        try:
            await self.connect()
            if self.redis_client is None:
                return False
            
            cache_key = self._get_cache_key(file_hash)
            await self.redis_client.delete(cache_key)
            logger.info(f"缓存已删除: {file_hash[:8]}...")
            return True
            
        except Exception as e:
            logger.warning(f"删除缓存失败: {e}")
            return False
    
    async def get_cached_result_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        根据文件hash获取缓存的解析结果
        返回: 解析结果字典，如果不存在则返回None
        """
        try:
            await self.connect()
            if self.redis_client is None:
                return None
            
            cache_key = self._get_cache_key(file_hash)
            
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                logger.info(f"缓存命中: {file_hash[:8]}...")
                return json.loads(cached_data)
            
            logger.debug(f"缓存未命中: {file_hash[:8]}...")
            return None
            
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")
            return None
    
    async def clear_all_cache(self) -> int:
        """
        清空所有解析缓存
        返回: 删除的缓存数量
        """
        try:
            await self.connect()
            if self.redis_client is None:
                return 0
            
            pattern = f"{self.cache_prefix}*"
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                count = await self.redis_client.delete(*keys)
                logger.info(f"已清空 {count} 个缓存项")
                return count
            
            return 0
            
        except Exception as e:
            logger.warning(f"清空缓存失败: {e}")
            return 0

# 全局缓存服务实例
cache_service = CacheService()

