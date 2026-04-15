"""配置系统测试。"""

import shutil
from pathlib import Path

from app.config import Settings, clear_settings_cache, get_settings


def test_default_settings():
    """测试默认配置值。"""
    settings = Settings()

    assert settings.APP_NAME == "AegisOTA"
    assert settings.DEBUG is False
    assert settings.DATABASE_URL == "sqlite:///./aegisota.db"
    assert settings.ARTIFACTS_DIR == Path("artifacts")


def test_settings_from_env(monkeypatch):
    """测试从环境变量读取配置。"""
    monkeypatch.setenv("AEGISOTA_DEBUG", "true")
    monkeypatch.setenv("AEGISOTA_DATABASE_URL", "sqlite:///./test.db")

    settings = Settings()

    assert settings.DEBUG is True
    assert settings.DATABASE_URL == "sqlite:///./test.db"


def test_artifacts_dir_creation():
    """测试产物目录创建。"""
    settings = Settings(ARTIFACTS_DIR=Path("test_artifacts"))

    assert settings.ARTIFACTS_DIR.exists()

    # 清理测试目录
    shutil.rmtree("test_artifacts", ignore_errors=True)


def test_clear_settings_cache():
    """测试清除配置缓存。"""
    # 获取缓存的配置实例
    settings1 = get_settings()
    settings2 = get_settings()

    # 验证是同一个实例（缓存生效）
    assert settings1 is settings2

    # 清除缓存
    clear_settings_cache()

    # 获取新实例
    settings3 = get_settings()

    # 验证是新实例（缓存已清除）
    assert settings3 is not settings1


class TestPoolConfig:
    """设备池配置测试。"""

    def test_pool_config_defaults(self):
        """测试设备池配置默认值。"""
        from app.config import Settings

        settings = Settings()

        assert settings.MAX_DEVICES_PER_POOL == 100
        assert settings.DEFAULT_POOL_RESERVED_RATIO == 0.2
        assert settings.SCHEDULER_INTERVAL_SEC == 5
        assert settings.MAX_QUEUED_RUNS == 1000
        assert settings.PREEMPTION_CHECK_INTERVAL == 10
        assert settings.ENABLE_DEVICE_POOL is True

    def test_pool_config_from_env(self, monkeypatch):
        """测试从环境变量读取配置。"""
        monkeypatch.setenv("AEGISOTA_MAX_DEVICES_PER_POOL", "200")
        monkeypatch.setenv("AEGISOTA_ENABLE_DEVICE_POOL", "false")

        from app.config import Settings, clear_settings_cache

        clear_settings_cache()
        settings = Settings()

        assert settings.MAX_DEVICES_PER_POOL == 200
        assert settings.ENABLE_DEVICE_POOL is False
