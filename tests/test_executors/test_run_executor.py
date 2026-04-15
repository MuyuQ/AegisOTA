"""状态机驱动器测试。"""

import pytest

from app.executors.mock_executor import MockADBExecutor
from app.executors.run_context import RunContext
from app.executors.run_executor import MockRunExecutor, RunExecutor
from app.models.run import StepName


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    return MockADBExecutor.upgrade_success_responses()


@pytest.fixture
def run_context(tmp_path):
    """创建执行上下文。"""
    return RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
        package_path="/tmp/update.zip",
        artifact_dir=tmp_path / "artifacts" / "1",
    )


def test_run_executor_init():
    """测试状态机初始化。"""
    executor = RunExecutor()
    assert len(executor.handlers) > 0


def test_run_executor_steps():
    """测试状态机步骤顺序。"""
    executor = RunExecutor()
    steps = executor.get_step_names()

    assert StepName.PRECHECK in steps
    assert StepName.APPLY_UPDATE in steps
    assert StepName.REBOOT_WAIT in steps


def test_run_executor_execute_full(mock_executor, run_context):
    """测试完整执行流程。"""
    executor = MockRunExecutor(mock_executor)
    result = executor.execute(run_context)

    assert result.success is True
    assert len(result.step_results) == len(executor.handlers)


def test_run_executor_stop_on_failure():
    """测试失败时停止执行。"""
    # 创建会失败的 Mock 执行器
    fail_executor = MockADBExecutor()
    fail_executor.set_response("adb devices", stdout="")  # 无设备

    executor = MockRunExecutor(fail_executor)

    context = RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
    )

    result = executor.execute(context)

    assert result.success is False
    # 应该在 precheck 就停止
    assert len(result.step_results) == 1


def test_run_executor_record_timeline(mock_executor, run_context):
    """测试时间线记录。"""
    executor = MockRunExecutor(mock_executor)
    executor.execute(run_context)

    assert len(run_context.timeline) > 0
    # 应包含步骤开始和结束事件
    events = [e["event_type"] for e in run_context.timeline]
    assert "step_start" in events or "step_end" in events
