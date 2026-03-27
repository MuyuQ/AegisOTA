"""阶段执行 Handler 测试。"""

import pytest
from pathlib import Path

from app.executors.step_handlers import (
    PrecheckHandler, PushPackageHandler,
    ApplyUpdateHandler, RebootWaitHandler,
    PostValidateHandler,
)
from app.executors.run_context import RunContext, DeviceSnapshot
from app.executors.mock_executor import MockADBExecutor
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


def test_precheck_handler_interface():
    """测试 Precheck Handler 接口。"""
    handler = PrecheckHandler()
    assert handler.step_name == StepName.PRECHECK
    assert hasattr(handler, 'execute')


def test_precheck_handler_success(mock_executor, run_context):
    """测试 Precheck 成功执行。"""
    handler = PrecheckHandler(executor=mock_executor)
    result = handler.execute(run_context)

    assert result.success is True
    assert "device_online" in result.data


def test_push_package_handler_success(mock_executor, run_context):
    """测试推送包成功。"""
    handler = PushPackageHandler(executor=mock_executor)
    result = handler.execute(run_context)

    assert result.success is True
    assert "push_time" in result.data


def test_apply_update_handler_interface():
    """测试 ApplyUpdate Handler 接口。"""
    handler = ApplyUpdateHandler()
    assert handler.step_name == StepName.APPLY_UPDATE


def test_reboot_wait_handler_timeout(mock_executor, run_context):
    """测试重启等待。"""
    handler = RebootWaitHandler(executor=mock_executor, timeout=60)
    result = handler.execute(run_context)

    assert result.success is True


def test_post_validate_handler_success(mock_executor, run_context):
    """测试升级后验证。"""
    handler = PostValidateHandler(executor=mock_executor)
    result = handler.execute(run_context)

    assert result.success is True