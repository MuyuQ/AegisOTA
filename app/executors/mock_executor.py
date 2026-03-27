"""Mock 命令执行器（用于测试）。"""

from typing import Optional, Dict, Tuple, List
from app.executors.command_runner import CommandRunner, CommandResult


class MockExecutor(CommandRunner):
    """Mock 命令执行器，用于测试场景。"""

    def __init__(self):
        self.responses: Dict[str, Tuple[int, str, str]] = {}
        self.executed_commands: List[str] = []
        self.default_exit_code: int = 0
        self.default_stdout: str = ""
        self.default_stderr: str = ""

    def set_response(
        self,
        command: str,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ):
        """设置特定命令的响应。"""
        self.responses[command] = (exit_code, stdout, stderr)

    def set_default_response(
        self,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ):
        """设置默认响应。"""
        self.default_exit_code = exit_code
        self.default_stdout = stdout
        self.default_stderr = stderr

    def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> CommandResult:
        """执行 Mock 命令。"""
        self.executed_commands.append(command)

        # 检查是否有预设响应（支持子串匹配）
        for cmd_pattern, (exit_code, stdout, stderr) in self.responses.items():
            # 检查是否完全匹配或包含该模式
            if command == cmd_pattern or cmd_pattern in command:
                return CommandResult(
                    command=command,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=10,
                )

        # 返回默认响应
        return CommandResult(
            command=command,
            exit_code=self.default_exit_code,
            stdout=self.default_stdout,
            stderr=self.default_stderr,
            duration_ms=10,
        )

    def clear(self):
        """清除所有记录。"""
        self.responses.clear()
        self.executed_commands.clear()

    @classmethod
    def default_device_responses(cls) -> "MockExecutor":
        """创建带有默认设备响应的 Mock 执行器。"""
        executor = cls()

        # 设备列表响应
        executor.set_response("adb devices", stdout="ABC123\tdevice\nXYZ789\tdevice\n")

        # getprop 响应（匹配任何 shell getprop 命令）
        executor.set_response(
            "shell getprop",
            stdout="""[ro.product.brand]: [Google]
[ro.product.model]: [Pixel 6]
[ro.build.version.release]: [14]
[ro.build.fingerprint]: [Google/oriole/oriole:14/AP1A.240305.019]
[sys.boot_completed]: [1]
"""
        )

        # 电量响应（匹配任何 dumpsys battery 命令）
        executor.set_response(
            "dumpsys battery",
            stdout="Current Battery Service state:\n  level: 85\n"
        )

        # 存储响应（匹配任何 df /data 命令）
        executor.set_response(
            "df /data",
            stdout="Filesystem      Size  Used Avail Use% Mounted on\n/dev/block/dm-0  64G   32G   32G  50% /data\n"
        )

        return executor

    @classmethod
    def upgrade_success_responses(cls) -> "MockExecutor":
        """创建升级成功场景的 Mock 响应。"""
        executor = cls.default_device_responses()

        # push 成功
        executor.set_response("adb push", stdout="push success\n")

        # 升级命令成功
        executor.set_response(
            "adb shell am broadcast",
            stdout="Broadcast completed: result=0\n"
        )

        return executor

    @classmethod
    def upgrade_failure_responses(cls) -> "MockExecutor":
        """创建升级失败场景的 Mock 响应。"""
        executor = cls.default_device_responses()

        # push 失败
        executor.set_response("adb push", exit_code=1, stderr="No space left on device\n")

        return executor