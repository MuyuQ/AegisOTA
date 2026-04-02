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
    """初始化数据库，创建所有表并添加示例数据。"""
    target_engine = db_engine or engine

    # 导入所有模型，确保它们注册到 Base.metadata
    from app.models.device import Device, DeviceLease, DevicePool  # noqa: F401
    from app.models.run import RunSession, RunStep, UpgradePlan  # noqa: F401
    from app.models.fault import FaultProfile  # noqa: F401
    from app.models.artifact import Artifact  # noqa: F401
    from app.models.report import Report  # noqa: F401

    Base.metadata.create_all(bind=target_engine)

    # 添加示例数据
    from sqlalchemy.orm import Session
    db = Session(target_engine)

    try:
        # 检查是否已有数据
        from app.models.device import Device, DevicePool, DeviceStatus
        from app.models.run import UpgradePlan, UpgradeType

        if db.query(Device).count() == 0:
            # 添加示例设备（Android 原生机）
            devices = [
                Device(serial="RF8N70XYZ123", brand="Samsung", model="Galaxy S24 Ultra", system_version="14", status=DeviceStatus.IDLE, battery_level=85, health_score=95),
                Device(serial="RF8N70XYZ124", brand="Xiaomi", model="14 Pro", system_version="14", status=DeviceStatus.IDLE, battery_level=92, health_score=98),
                Device(serial="RF8N70XYZ125", brand="OPPO", model="Find X7 Ultra", system_version="14", status=DeviceStatus.OFFLINE, battery_level=45, health_score=88),
                Device(serial="RF8N70XYZ126", brand="vivo", model="X100 Pro", system_version="14", status=DeviceStatus.IDLE, battery_level=78, health_score=92),
                Device(serial="RF8N70XYZ127", brand="Google", model="Pixel 8 Pro", system_version="14", status=DeviceStatus.BUSY, battery_level=65, health_score=90),
            ]
            for d in devices:
                db.add(d)
            db.commit()
            print("Added sample devices")

        if db.query(UpgradePlan).count() == 0:
            # 添加示例升级计划
            plans = [
                UpgradePlan(name="Android 14 全量升级", upgrade_type=UpgradeType.FULL, package_path="/data/ota/full_14.zip", target_build="HUAWEI.HMH.14.0.0"),
                UpgradePlan(name="Android 14 增量升级", upgrade_type=UpgradeType.INCREMENTAL, package_path="/data/ota/inc_14.zip", target_build="HUAWEI.HMH.14.0.1"),
                UpgradePlan(name="版本回滚测试", upgrade_type=UpgradeType.ROLLBACK, package_path="/data/ota/rollback.zip", target_build="HUAWEI.HMH.13.0.0"),
            ]
            for p in plans:
                db.add(p)
            db.commit()
            print("Added sample upgrade plans")

    except Exception as e:
        print(f"Error adding sample data: {e}")
    finally:
        db.close()