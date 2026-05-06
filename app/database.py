"""数据库连接管理模块。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 需要此参数
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
    """初始化数据库表结构。

    仅创建表，不写入演示数据。如需示例数据，请运行：
        uv run app/cli/main.py seed
    """
    target_engine = db_engine or engine

    # 导入所有模型，确保它们注册到 Base.metadata
    from app.models.artifact import Artifact  # noqa: F401
    from app.models.device import Device, DeviceLease, DevicePool  # noqa: F401
    from app.models.diagnostic import (  # noqa: F401
        DiagnosticResult,
        DiagnosticRule,
        NormalizedEvent,
        RuleHit,
        SimilarCaseIndex,
    )
    from app.models.fault import FaultProfile  # noqa: F401
    from app.models.report import Report  # noqa: F401
    from app.models.run import RunSession, RunStep, UpgradePlan  # noqa: F401

    Base.metadata.create_all(bind=target_engine)
