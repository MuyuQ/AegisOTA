"""数据库连接管理模块。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 需要此参数
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话（用于 FastAPI dependency）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(db_engine=None):
    """初始化数据库，创建所有表。"""
    target_engine = db_engine or engine
    Base.metadata.create_all(bind=target_engine)