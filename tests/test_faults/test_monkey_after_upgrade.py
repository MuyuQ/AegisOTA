"""Monkey 测试插件测试。"""

import pytest

from app.executors.mock_executor import MockADBExecutor
from app.executors.run_context import RunContext
from app.faults.monkey_after_upgrade import MonkeyAfterUpgradeFault


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    executor = MockADBExecutor()
    executor.set_response(
        "monkey",
        stdout=(
            "Events injected: 1000\n:Dropped: 0\n:Crashed: 0\n## Network stats: elapsed time=5s\n"
        ),
    )
    return executor


@pytest.fixture
def run_context(tmp_path):
    """创建执行上下文。"""
    return RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
        artifact_dir=tmp_path / "artifacts" / "1",
    )


def test_monkey_plugin_init():
    """测试插件初始化。"""
    plugin = MonkeyAfterUpgradeFault()
    assert plugin.fault_type == "monkey_after_upgrade"
    assert plugin.fault_stage == "post_validate"


def test_monkey_plugin_inject(mock_executor, run_context):
    """测试 Monkey 注入。"""
    plugin = MonkeyAfterUpgradeFault(executor=mock_executor)
    plugin.set_parameters({"event_count": 1000})

    result = plugin.inject(run_context)

    assert result.success is True
    assert "events_injected" in result.data


def test_monkey_plugin_parse_results(mock_executor, run_context):
    """测试解析 Monkey 结果。"""
    plugin = MonkeyAfterUpgradeFault(executor=mock_executor)

    result = plugin.inject(run_context)

    assert result.data["events_injected"] >= 0


def test_monkey_plugin_with_crash(run_context, tmp_path):
    """测试 Monkey 发现崩溃。"""
    executor = MockADBExecutor()
    executor.set_response(
        "monkey",
        stdout=(
            "Events injected: 500\n"
            ":Crashed: 1\n"
            "** Monkey aborted due to crash\n"
            "## Network stats: elapsed time=5s\n"
        ),
    )

    plugin = MonkeyAfterUpgradeFault(executor=executor)
    result = plugin.inject(run_context)

    # 有崩溃但插件仍应完成
    assert result.success is True
    assert result.data.get("crashed", 0) > 0
