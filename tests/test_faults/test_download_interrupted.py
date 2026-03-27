"""下载中断注入测试。"""

import pytest

from app.faults.download_interrupted import DownloadInterruptedFault
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockADBExecutor


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    executor = MockADBExecutor()
    executor.set_response("rm", stdout="")
    executor.set_response("ls", stdout="")
    return executor


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


def test_download_interrupted_plugin_init():
    """测试插件初始化。"""
    plugin = DownloadInterruptedFault()
    assert plugin.fault_type == "download_interrupted"
    assert plugin.fault_stage == "precheck"


def test_download_interrupted_inject(mock_executor, run_context):
    """测试下载中断注入。"""
    plugin = DownloadInterruptedFault(executor=mock_executor)
    plugin.set_parameters({"interrupt_point": "before_download"})

    result = plugin.inject(run_context)

    assert result.success is True