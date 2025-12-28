from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# 数据库引擎 - 配置连接池
engine = create_engine(
    settings.database_url,
    pool_size=10,              # 连接池大小
    max_overflow=20,           # 最大溢出连接数
    pool_pre_ping=True,        # 连接前检查连接是否有效
    pool_recycle=3600,         # 连接回收时间（秒），避免长时间连接失效
    echo=settings.debug        # 调试模式下打印SQL
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()

# 依赖注入
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # 发生异常时回滚事务，避免脏会话
        db.rollback()
        raise
    finally:
        db.close()