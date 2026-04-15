"""配置管理模块。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    SCHEDULER_INTERVAL_SEC: int = 5  # 调度器间隔（秒）
    MAX_QUEUED_RUNS: int = 1000  # 最大排队任务数
    PREEMPTION_CHECK_INTERVAL: int = 10  # 抢占检查间隔（秒）

    # 设备池配置
    ENABLE_DEVICE_POOL: bool = True  # 设备池功能开关
    MAX_DEVICES_PER_POOL: int = 100  # 单池最大设备数
    DEFAULT_POOL_RESERVED_RATIO: float = 0.2  # 默认应急保留比例

    # API Key 认证配置
    API_KEY_ENABLED: bool = True  # API Key 认证开关
    API_KEY_HEADER: str = "X-API-Key"  # API Key 请求头名称
    API_KEYS: list[str] = []  # 有效的 API Keys（环境变量逗号分隔）

    # 日志配置
    LOG_LEVEL: str = "INFO"  # 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)

    # 升级包配置
    OTA_PACKAGES_DIR: Path = Path("ota_packages")  # 升级包根目录
    FULL_PACKAGE_SUBDIR: str = "full"  # 全量包子目录
    INCREMENTAL_PACKAGE_SUBDIR: str = "incremental"  # 差分包子目录

    # 相似案例召回配置
    SIMILARITY_THRESHOLD: float = 0.3  # 最低相似度阈值
    SIMILARITY_ROOT_CAUSE_WEIGHT: float = 0.5  # 根因完全匹配权重
    SIMILARITY_CATEGORY_WEIGHT: float = 0.2  # 分类匹配权重
    SIMILARITY_EVIDENCE_WEIGHT: float = 0.3  # 证据哈希相似度权重
    SIMILAR_CASE_LIMIT: int = 3  # 相似案例召回数量

    model_config = SettingsConfigDict(
        env_prefix="AEGISOTA_",
        env_file=".env",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保产物目录存在，应用启动时自动创建
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        # 确保升级包目录存在
        self.OTA_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
        (self.OTA_PACKAGES_DIR / self.FULL_PACKAGE_SUBDIR).mkdir(parents=True, exist_ok=True)
        (self.OTA_PACKAGES_DIR / self.INCREMENTAL_PACKAGE_SUBDIR).mkdir(parents=True, exist_ok=True)

    def get_full_package_path(self) -> Path:
        """获取全量包目录路径。"""
        return self.OTA_PACKAGES_DIR / self.FULL_PACKAGE_SUBDIR

    def get_incremental_package_path(self) -> Path:
        """获取差分包目录路径。"""
        return self.OTA_PACKAGES_DIR / self.INCREMENTAL_PACKAGE_SUBDIR


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（缓存）。"""
    return Settings()


def clear_settings_cache() -> None:
    """清除配置缓存。

    用于测试环境重置配置状态。
    """
    get_settings.cache_clear()
