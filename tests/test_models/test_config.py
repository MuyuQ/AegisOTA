"""配置系统测试。"""

import os
from pathlib import Path

import pytest

from app.config import Settings


def test_default_settings():
    """测试默认配置值。"""
    settings = Settings()

    assert settings.APP_NAME == "AegisOTA"
    assert settings.DEBUG is False
    assert settings.DATABASE_URL == "sqlite:///./aegisota.db"
    assert settings.ARTIFACTS_DIR == Path("artifacts")


def test_settings_from_env():
    """测试从环境变量读取配置。"""
    os.environ["AEGISOTA_DEBUG"] = "true"
    os.environ["AEGISOTA_DATABASE_URL"] = "sqlite:///./test.db"

    settings = Settings()

    assert settings.DEBUG is True
    assert settings.DATABASE_URL == "sqlite:///./test.db"

    # 清理环境变量
    del os.environ["AEGISOTA_DEBUG"]
    del os.environ["AEGISOTA_DATABASE_URL"]


def test_artifacts_dir_creation():
    """测试产物目录创建。"""
    settings = Settings(ARTIFACTS_DIR=Path("test_artifacts"))

    assert settings.ARTIFACTS_DIR.exists()

    # 清理测试目录
    import shutil
    shutil.rmtree("test_artifacts", ignore_errors=True)