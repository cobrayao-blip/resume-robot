"""
应用常量配置
"""
# 文件上传限制
MAX_FILE_SIZE_MB = 10
MAX_TEXT_LENGTH = 25000

# 缓存配置
CACHE_TTL_HOURS = 24
CACHE_TTL_SECONDS = CACHE_TTL_HOURS * 3600

# 允许的文件类型
ALLOWED_FILE_TYPES = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword'
]

# 允许的文件扩展名
ALLOWED_FILE_EXTENSIONS = ['.pdf', '.docx', '.doc']

# JWT Token 配置
DEFAULT_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# 分页配置
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# API 响应消息
SUCCESS_MESSAGE = "操作成功"
ERROR_MESSAGE = "操作失败"

# 数据库连接池配置
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_POOL_RECYCLE = 3600  # 1小时

# Redis 连接池配置
REDIS_MAX_CONNECTIONS = 50

