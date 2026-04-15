"""ADB 执行器测试。"""

from app.executors.adb_executor import ADBExecutor


def test_adb_executor_init():
    """测试 ADB 执行器初始化。"""
    executor = ADBExecutor()
    assert executor.adb_path == "adb"
    assert executor.fastboot_path == "fastboot"


def test_adb_executor_init_custom_path():
    """测试自定义 ADB 路径。"""
    executor = ADBExecutor(adb_path="/custom/adb")
    assert executor.adb_path == "/custom/adb"


def test_adb_devices_command_format():
    """测试 adb devices 命令格式。"""
    executor = ADBExecutor()
    cmd = executor._build_adb_command("devices")
    assert cmd == ["adb", "devices"]


def test_adb_shell_command_format():
    """测试 adb shell 命令格式。"""
    executor = ADBExecutor()
    cmd = executor._build_adb_command("shell", "getprop", device="ABC123")
    assert cmd == ["adb", "-s", "ABC123", "shell", "getprop"]


def test_adb_push_command_format():
    """测试 adb push 命令格式。"""
    executor = ADBExecutor()
    cmd = executor._build_adb_command("push", "/local/file", "/remote/path", device="ABC123")
    assert cmd == ["adb", "-s", "ABC123", "push", "/local/file", "/remote/path"]


def test_adb_executor_interface():
    """测试 ADB 执行器接口方法。"""
    executor = ADBExecutor()
    assert hasattr(executor, "devices")
    assert hasattr(executor, "shell")
    assert hasattr(executor, "push")
    assert hasattr(executor, "reboot")
    assert hasattr(executor, "getprop")
