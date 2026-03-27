"""配置管理模块。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置。"""

    APP_NAME: str = "AegisOTA"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite:///./aegisota.db"
    ARTIFACTS_DIR: Path = Path("artifacts")

    # 设备管理配置
    DEVICE_SYNC_INTERVAL: int = 60  # 设备同步间隔（秒）
    DEVICE_HEALTH_CHECK_INTERVAL: int = 30  # 健康检查间隔

    # 任务执行配置
    DEFAULT_TIMEOUT: int = 300  # 默认超时时间（秒）
    REBOOT_WAIT_TIMEOUT: int = 120  # 重启等待超时
    BOOT_COMPLETE_TIMEOUT: int = 90  # 开机完成超时

    # Monkey 配置
    MONKEY_DEFAULT_COUNT: int = 1000  # 默认 Monkey 事件数
    MONKEY_THROTTLE: int = 50  # Monkey 事件间隔（毫秒）

    # 调度配置
    MAX_CONCURRENT_RUNS: int = 5  # 最大并发任务数
    LEASE_DEFAULT_DURATION: int = 3600  # 默认租约时长（秒）

    model_config = {
        "env_prefix": "AEGISOTA_",
        "env_file": ".env",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（缓存）。"""
    return Settings()