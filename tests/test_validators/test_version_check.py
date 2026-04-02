"""版本确认测试。"""

import pytest

from app.validators.version_check import VersionChecker
from app.executors.mock_executor import MockADBExecutor


def test_version_checker_success():
    """测试版本确认成功。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell getprop",
        stdout="[ro.build.fingerprint]: [Google/oriole/oriole:14/AP1A.240305.019]\n"
    )

    checker = VersionChecker(executor)
    result = checker.check("ABC123", expected="AP1A.240305.019")

    assert result.passed is True
    assert result.current_version == "Google/oriole/oriole:14/AP1A.240305.019"


def test_version_checker_mismatch():
    """测试版本不匹配。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell getprop",
        stdout="[ro.build.fingerprint]: [Google/oriole/oriole:13/OLD_VERSION]\n"
    )

    checker = VersionChecker(executor)
    result = checker.check("ABC123", expected="AP1A.240305.019")

    assert result.passed is False
    # 检查中文"不匹配"
    assert "不匹配" in result.message


def test_version_checker_get_version():
    """测试获取版本信息。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell getprop",
        stdout="[ro.build.version.release]: [14]\n[ro.build.fingerprint]: [TEST_FP]\n"
    )

    checker = VersionChecker(executor)
    version_info = checker.get_version_info("ABC123")

    assert version_info["system_version"] == "14"
    assert version_info["build_fingerprint"] == "TEST_FP"