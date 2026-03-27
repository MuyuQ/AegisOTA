"""开机检测测试。"""

import pytest

from app.validators.boot_check import BootChecker
from app.executors.mock_executor import MockADBExecutor


def test_boot_checker_success():
    """测试开机检测成功。"""
    executor = MockADBExecutor()
    # 设置完整的 getprop 响应
    executor.set_response(
        "shell getprop",
        stdout="[sys.boot_completed]: [1]\n"
    )

    checker = BootChecker(executor)
    result = checker.check("ABC123")

    assert result.passed is True


def test_boot_checker_failure():
    """测试开机检测失败。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell getprop",
        stdout="[sys.boot_completed]: [0]\n"
    )

    checker = BootChecker(executor)
    result = checker.check("ABC123")

    assert result.passed is False


def test_boot_checker_timeout():
    """测试开机检测超时。"""
    executor = MockADBExecutor()
    # 返回空响应模拟超时
    executor.set_response("shell getprop", stdout="")

    checker = BootChecker(executor, timeout=30)
    result = checker.check("ABC123")

    assert result.passed is False


def test_boot_checker_with_wait():
    """测试等待开机完成。"""
    executor = MockADBExecutor()
    # 设置响应返回 boot_completed=1
    executor.set_response("shell getprop", stdout="[sys.boot_completed]: [1]\n")

    checker = BootChecker(executor)
    result = checker.wait_for_boot("ABC123", timeout=60)

    assert result.passed is True