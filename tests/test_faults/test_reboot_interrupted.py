"""重启中断注入测试。"""

import pytest

from app.faults.reboot_interrupted import RebootInterruptedFault
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockADBExecutor


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    executor = MockADBExecutor()
    executor.set_response("reboot", stdout="")
    executor.set_response("shell exit", stdout="")
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


def test_reboot_interrupted_plugin_init():
    """测试插件初始化。"""
    plugin = RebootInterruptedFault()
    assert plugin.fault_type == "reboot_interrupted"
    assert plugin.fault_stage == "apply_update"


def test_reboot_interrupted_prepare(mock_executor, run_context):
    """测试准备阶段。"""
    plugin = RebootInterruptedFault(executor=mock_executor)
    result = plugin.prepare(run_context)

    assert result.success is True


def test_reboot_interrupted_inject(mock_executor, run_context):
    """测试注入阶段。"""
    plugin = RebootInterruptedFault(executor=mock_executor)
    plugin.set_parameters({"interrupt_after_seconds": 0})  # 使用 0 秒避免实际 sleep

    result = plugin.inject(run_context)

    # Mock 执行器应该返回成功
    assert result.success is True


def test_reboot_interrupted_validate_parameters():
    """测试参数验证。"""
    plugin = RebootInterruptedFault()

    plugin.set_parameters({"interrupt_after_seconds": 10})
    assert plugin.validate_parameters() is True

    plugin.set_parameters({"interrupt_after_seconds": -1})
    assert plugin.validate_parameters() is False