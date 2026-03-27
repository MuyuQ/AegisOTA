"""Monkey 执行器测试。"""

import pytest

from app.validators.monkey_runner import MonkeyRunner, MonkeyResult
from app.executors.mock_executor import MockADBExecutor


def test_monkey_runner_init():
    """测试 Monkey 执行器初始化。"""
    runner = MonkeyRunner()
    assert runner.default_event_count == 1000


def test_monkey_runner_custom_config():
    """测试自定义配置。"""
    runner = MonkeyRunner(event_count=5000, throttle=100)
    assert runner.event_count == 5000
    assert runner.throttle == 100


def test_monkey_runner_execute_success():
    """测试 Monkey 执行成功。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell monkey",
        stdout="Events injected: 1000\n:Dropped: 0\n:Crashed: 0\n## Network stats: 0\n"
    )

    runner = MonkeyRunner(executor=executor)
    result = runner.run("ABC123")

    assert result.success is True
    assert result.events_injected == 1000


def test_monkey_runner_parse_output():
    """测试解析 Monkey 输出。"""
    runner = MonkeyRunner()

    output = """Events injected: 1000
:Dropped: 5
:Crashed: 0
## Network stats: elapsed time=10s
"""

    stats = runner.parse_output(output)
    assert stats["events_injected"] == 1000
    assert stats["dropped"] == 5
    assert stats["crashed"] == 0


def test_monkey_runner_with_crash():
    """测试 Monkey 发现崩溃。"""
    executor = MockADBExecutor()
    executor.set_response(
        "shell monkey",
        stdout="Events injected: 500\n:Crashed: 1\n** Monkey aborted **\n"
    )

    runner = MonkeyRunner(executor=executor)
    result = runner.run("ABC123")

    assert result.success is True  # 执行完成，但发现崩溃
    assert result.crashed == 1


def test_monkey_result_to_dict():
    """测试 Monkey 结果转换。"""
    result = MonkeyResult(
        success=True,
        events_injected=1000,
        dropped=0,
        crashed=0,
        timeout=0,
        network_errors=0,
        duration_ms=5000,
        aborted=False,
    )

    data = result.to_dict()
    assert data["events_injected"] == 1000
    assert data["success"] is True


def test_monkey_result_is_stable():
    """测试稳定性判断。"""
    # 稳定情况
    stable_result = MonkeyResult(
        success=True,
        events_injected=1000,
        dropped=0,
        crashed=0,
        timeout=0,
        network_errors=0,
        duration_ms=5000,
        aborted=False,
    )
    assert stable_result.is_stable() is True

    # 有崩溃的情况
    crashed_result = MonkeyResult(
        success=True,
        events_injected=500,
        dropped=0,
        crashed=1,
        timeout=0,
        network_errors=0,
        duration_ms=5000,
        aborted=False,
    )
    assert crashed_result.is_stable() is False

    # 被中止的情况
    aborted_result = MonkeyResult(
        success=True,
        events_injected=100,
        dropped=0,
        crashed=0,
        timeout=0,
        network_errors=0,
        duration_ms=5000,
        aborted=True,
    )
    assert aborted_result.is_stable() is False