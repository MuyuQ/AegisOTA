"""Mock 执行器测试。"""

from app.executors.mock_executor import MockExecutor


def test_mock_executor_returns_success():
    """测试 Mock 执行器返回成功。"""
    executor = MockExecutor()
    result = executor.run("echo test")

    assert result.success is True
    assert result.exit_code == 0


def test_mock_executor_custom_response():
    """测试自定义 Mock 响应。"""
    executor = MockExecutor()
    executor.set_response("adb devices", stdout="ABC123\tdevice\n")

    result = executor.run("adb devices")
    assert result.stdout == "ABC123\tdevice\n"


def test_mock_executor_failure_response():
    """测试失败响应。"""
    executor = MockExecutor()
    executor.set_response("false", exit_code=1, stderr="command failed")

    result = executor.run("false")
    assert result.success is False
    assert result.exit_code == 1


def test_mock_executor_records_commands():
    """测试记录执行的命令。"""
    executor = MockExecutor()
    executor.run("adb devices")
    executor.run("adb shell getprop")

    assert len(executor.executed_commands) == 2
    assert "adb devices" in executor.executed_commands


def test_mock_executor_default_device_response():
    """测试默认设备响应。"""
    executor = MockExecutor.default_device_responses()

    result = executor.run("adb devices")
    assert "device" in result.stdout

    result = executor.run("adb -s ABC123 shell getprop ro.product.model")
    assert result.success
