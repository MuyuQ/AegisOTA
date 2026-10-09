"""缺失故障类型测试。"""

import pytest

from app.executors.mock_executor import MockADBExecutor
from app.executors.run_context import RunContext
from app.faults.low_battery import LowBatteryFault
from app.faults.package_corrupted import PackageCorruptedFault
from app.faults.performance_regression import PerformanceRegressionFault
from app.faults.post_boot_watchdog_failure import PostBootWatchdogFailureFault


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


class TestPackageCorruptedFault:
    """包损坏故障测试。"""

    def test_fault_type_and_stage(self):
        """测试故障类型和阶段。"""
        fault = PackageCorruptedFault()
        assert fault.fault_type == "package_corrupted"
        assert fault.fault_stage == "precheck"

    def test_validate_parameters(self):
        """测试参数验证。"""
        fault = PackageCorruptedFault(corruption_type="header")
        assert fault.validate_parameters() is True

        fault = PackageCorruptedFault(corruption_type="truncate")
        assert fault.validate_parameters() is True

        fault = PackageCorruptedFault(corruption_type="append")
        assert fault.validate_parameters() is True

        fault = PackageCorruptedFault(corruption_type="invalid")
        assert fault.validate_parameters() is False

    def test_prepare(self, mock_executor, run_context):
        """测试准备阶段。"""
        fault = PackageCorruptedFault(executor=mock_executor)
        result = fault.prepare(run_context)

        assert result.success is True
        assert "corruption_type" in result.data

    def test_inject_header(self, mock_executor, run_context):
        """测试头部损坏注入。"""
        fault = PackageCorruptedFault(
            executor=mock_executor,
            corruption_type="header",
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "header" in result.message

    def test_inject_truncate(self, mock_executor, run_context):
        """测试截断损坏注入。"""
        fault = PackageCorruptedFault(
            executor=mock_executor,
            corruption_type="truncate",
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "truncate" in result.message

    def test_inject_append(self, mock_executor, run_context):
        """测试追加损坏注入。"""
        fault = PackageCorruptedFault(
            executor=mock_executor,
            corruption_type="append",
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "append" in result.message

    def test_cleanup(self, mock_executor, run_context):
        """测试清理阶段。"""
        fault = PackageCorruptedFault(executor=mock_executor)
        result = fault.cleanup(run_context)

        assert result.success is True


class TestLowBatteryFault:
    """低电量故障测试。"""

    def test_fault_type_and_stage(self):
        """测试故障类型和阶段。"""
        fault = LowBatteryFault()
        assert fault.fault_type == "low_battery"
        assert fault.fault_stage == "precheck"

    def test_validate_parameters(self):
        """测试参数验证。"""
        fault = LowBatteryFault(battery_level=5)
        assert fault.validate_parameters() is True

        fault = LowBatteryFault(battery_level=100)
        assert fault.validate_parameters() is True

        fault = LowBatteryFault(battery_level=-1)
        assert fault.validate_parameters() is False

        fault = LowBatteryFault(battery_level=101)
        assert fault.validate_parameters() is False

    def test_prepare(self, mock_executor, run_context):
        """测试准备阶段。"""
        fault = LowBatteryFault(executor=mock_executor)
        result = fault.prepare(run_context)

        assert result.success is True

    def test_inject(self, mock_executor, run_context):
        """测试低电量注入。"""
        fault = LowBatteryFault(
            executor=mock_executor,
            battery_level=5,
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "battery_level" in result.data

    def test_cleanup(self, mock_executor, run_context):
        """测试清理阶段。"""
        fault = LowBatteryFault(executor=mock_executor)
        # 先执行注入以保存原始电量
        fault.inject(run_context)
        result = fault.cleanup(run_context)

        assert result.success is True


class TestPostBootWatchdogFailureFault:
    """启动后 Watchdog 故障测试。"""

    def test_fault_type_and_stage(self):
        """测试故障类型和阶段。"""
        fault = PostBootWatchdogFailureFault()
        assert fault.fault_type == "post_boot_watchdog_failure"
        assert fault.fault_stage == "post_validate"

    def test_validate_parameters(self):
        """测试参数验证。"""
        fault = PostBootWatchdogFailureFault(failure_type="system_server_crash")
        assert fault.validate_parameters() is True

        fault = PostBootWatchdogFailureFault(failure_type="boot_loop")
        assert fault.validate_parameters() is True

        fault = PostBootWatchdogFailureFault(failure_type="anr")
        assert fault.validate_parameters() is True

        fault = PostBootWatchdogFailureFault(failure_type="invalid")
        assert fault.validate_parameters() is False

    def test_prepare(self, mock_executor, run_context):
        """测试准备阶段。"""
        fault = PostBootWatchdogFailureFault(executor=mock_executor)
        result = fault.prepare(run_context)

        assert result.success is True
        assert "failure_type" in result.data

    def test_inject_system_server_crash(self, mock_executor, run_context):
        """测试 system_server 崩溃注入。"""
        fault = PostBootWatchdogFailureFault(
            executor=mock_executor,
            failure_type="system_server_crash",
            delay_seconds=0,  # 跳过等待加快测试
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "system_server" in result.message

    def test_inject_boot_loop(self, mock_executor, run_context):
        """测试启动循环注入。"""
        fault = PostBootWatchdogFailureFault(
            executor=mock_executor,
            failure_type="boot_loop",
            delay_seconds=0,
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "boot_completed" in result.message.lower()

    def test_inject_anr(self, mock_executor, run_context):
        """测试 ANR 注入。"""
        fault = PostBootWatchdogFailureFault(
            executor=mock_executor,
            failure_type="anr",
            delay_seconds=0,
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "ANR" in result.message

    def test_cleanup(self, mock_executor, run_context):
        """测试清理阶段。"""
        fault = PostBootWatchdogFailureFault(executor=mock_executor)
        result = fault.cleanup(run_context)

        assert result.success is True


class TestPerformanceRegressionFault:
    """性能退化故障测试。"""

    def test_fault_type_and_stage(self):
        """测试故障类型和阶段。"""
        fault = PerformanceRegressionFault()
        assert fault.fault_type == "performance_regression"
        assert fault.fault_stage == "post_validate"

    def test_validate_parameters(self):
        """测试参数验证。"""
        fault = PerformanceRegressionFault(pressure_type="cpu")
        assert fault.validate_parameters() is True

        fault = PerformanceRegressionFault(pressure_type="memory")
        assert fault.validate_parameters() is True

        fault = PerformanceRegressionFault(pressure_type="io")
        assert fault.validate_parameters() is True

        fault = PerformanceRegressionFault(pressure_type="invalid")
        assert fault.validate_parameters() is False

    def test_prepare(self, mock_executor, run_context):
        """测试准备阶段。"""
        fault = PerformanceRegressionFault(executor=mock_executor)
        result = fault.prepare(run_context)

        assert result.success is True

    def test_inject_cpu(self, mock_executor, run_context):
        """测试 CPU 压力注入。"""
        fault = PerformanceRegressionFault(
            executor=mock_executor,
            pressure_type="cpu",
            duration_seconds=1,  # 最短时间加快测试
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "cpu" in result.message.lower()

    def test_inject_memory(self, mock_executor, run_context):
        """测试内存压力注入。"""
        fault = PerformanceRegressionFault(
            executor=mock_executor,
            pressure_type="memory",
            duration_seconds=1,
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "memory" in result.message.lower()

    def test_inject_io(self, mock_executor, run_context):
        """测试 IO 压力注入。"""
        fault = PerformanceRegressionFault(
            executor=mock_executor,
            pressure_type="io",
            duration_seconds=1,
        )
        result = fault.inject(run_context)

        assert result.success is True
        assert "io" in result.message.lower()

    def test_cleanup(self, mock_executor, run_context):
        """测试清理阶段。"""
        fault = PerformanceRegressionFault(executor=mock_executor)
        result = fault.cleanup(run_context)

        assert result.success is True
