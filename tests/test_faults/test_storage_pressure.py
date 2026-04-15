"""存储压力注入测试。"""

import pytest

from app.executors.mock_executor import MockADBExecutor
from app.executors.run_context import RunContext
from app.faults.storage_pressure import StoragePressureFault


@pytest.fixture
def mock_executor():
    """创建 Mock ADB 执行器。"""
    executor = MockADBExecutor()
    # df 输出只返回数据行（模拟 | tail -1 的效果）
    executor.set_response(
        "df /data", stdout="/dev/block/dm-0  65536   32768     32768  50% /data\n"
    )
    # dd 命令返回空输出（成功）
    executor.set_response("dd if=/dev/zero", stdout="")
    # rm 命令返回空输出（成功）
    executor.set_response("rm -f", stdout="")
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


def test_storage_pressure_plugin_init():
    """测试插件初始化。"""
    plugin = StoragePressureFault()
    assert plugin.fault_type == "storage_pressure"
    assert plugin.fault_stage == "precheck"


def test_storage_pressure_prepare(mock_executor, run_context):
    """测试准备阶段。"""
    plugin = StoragePressureFault(executor=mock_executor)
    plugin.set_parameters({"fill_percent": 90})

    result = plugin.prepare(run_context)

    assert result.success is True


def test_storage_pressure_inject(mock_executor, run_context):
    """测试注入阶段。"""
    plugin = StoragePressureFault(executor=mock_executor)
    plugin.set_parameters({"fill_percent": 90})

    result = plugin.inject(run_context)

    assert result.success is True
    assert "fill_percent" in result.data


def test_storage_pressure_cleanup(mock_executor, run_context):
    """测试清理阶段。"""
    plugin = StoragePressureFault(executor=mock_executor)
    plugin.set_parameters({"fill_percent": 90})

    # 先注入
    plugin.inject(run_context)

    # 再清理
    result = plugin.cleanup(run_context)

    assert result.success is True


def test_storage_pressure_validate_parameters():
    """测试参数验证。"""
    plugin = StoragePressureFault()

    # 有效参数
    plugin.set_parameters({"fill_percent": 50})
    assert plugin.validate_parameters() is True

    # 无效参数（超出范围）
    plugin.set_parameters({"fill_percent": 150})
    assert plugin.validate_parameters() is False
