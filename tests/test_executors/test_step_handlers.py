"""阶段执行 Handler 测试。"""

import pytest

from app.executors.mock_executor import MockADBExecutor
from app.executors.run_context import RunContext
from app.executors.step_handlers import (
    ApplyUpdateHandler,
    PostValidateHandler,
    PrecheckHandler,
    PushPackageHandler,
    RebootWaitHandler,
)
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
    assert hasattr(handler, "execute")


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


class TestIdempotency:
    """幂等性测试类。"""

    def test_execute_with_idempotency_skips_when_can_resume(self, mock_executor, run_context):
        """测试当 can_resume 返回 True 时跳过执行。"""
        handler = PrecheckHandler(executor=mock_executor)

        # 先执行一次
        result1 = handler.execute(run_context)
        assert result1.success is True
        assert result1.skipped is False

        # 保存结果到上下文
        run_context.step_results[StepName.PRECHECK.value] = result1.to_dict()

        # 再次执行时应该跳过
        result2 = handler.execute_with_idempotency(run_context, enable_idempotency=True)

        assert result2.success is True
        assert result2.skipped is True

    def test_execute_with_idempotency_disabled(self, mock_executor, run_context):
        """测试禁用幂等性时仍然执行。"""
        handler = PrecheckHandler(executor=mock_executor)

        # 先执行一次
        result1 = handler.execute(run_context)
        run_context.step_results[StepName.PRECHECK.value] = result1.to_dict()

        # 禁用幂等性时仍然执行
        result2 = handler.execute_with_idempotency(run_context, enable_idempotency=False)

        assert result2.success is True
        assert result2.skipped is False

    def test_can_resume_returns_false_without_previous_result(self, mock_executor, run_context):
        """测试没有之前结果时 can_resume 返回 False。"""
        handler = PrecheckHandler(executor=mock_executor)

        # 没有之前的结果
        assert handler.can_resume(run_context) is False

    def test_can_resume_returns_true_with_success_result(self, mock_executor, run_context):
        """测试有成功结果时 can_resume 返回 True。"""
        handler = PrecheckHandler(executor=mock_executor)

        # 先执行一次
        result = handler.execute(run_context)
        run_context.step_results[StepName.PRECHECK.value] = result.to_dict()

        # 设备仍然在线
        assert handler.can_resume(run_context) is True

    def test_push_package_can_resume(self, mock_executor, run_context):
        """测试推送包幂等性检查。"""
        handler = PushPackageHandler(executor=mock_executor)

        # 没有之前结果
        assert handler.can_resume(run_context) is False

        # 执行一次
        result = handler.execute(run_context)
        run_context.step_results[StepName.PACKAGE_PREPARE.value] = result.to_dict()

        # 设置 mock 响应使文件检查通过
        mock_executor.set_response("ls -la", stdout="/data/local/tmp/update.zip")

        # 现在应该可以跳过
        assert handler.can_resume(run_context) is True

    def test_reboot_wait_can_resume(self, mock_executor, run_context):
        """测试重启等待幂等性检查。"""
        handler = RebootWaitHandler(executor=mock_executor)

        # 没有之前结果
        assert handler.can_resume(run_context) is False

        # 执行一次
        result = handler.execute(run_context)
        run_context.step_results[StepName.REBOOT_WAIT.value] = result.to_dict()

        # 设备仍然启动完成
        assert handler.can_resume(run_context) is True

    def test_post_validate_can_resume(self, mock_executor, run_context):
        """测试升级后验证幂等性检查。"""
        handler = PostValidateHandler(executor=mock_executor)

        # 没有之前结果
        assert handler.can_resume(run_context) is False

        # 执行一次
        result = handler.execute(run_context)
        run_context.step_results[StepName.POST_VALIDATE.value] = result.to_dict()

        # 验证仍然通过
        assert handler.can_resume(run_context) is True

    def test_result_to_dict_includes_skipped(self, mock_executor, run_context):
        """测试结果包含 skipped 字段。"""
        handler = PrecheckHandler(executor=mock_executor)
        result = handler.execute(run_context)

        result_dict = result.to_dict()
        assert "skipped" in result_dict
        assert result_dict["skipped"] is False
