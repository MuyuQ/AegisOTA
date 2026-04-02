"""Mock 命令执行器（用于测试）。"""

import re
from typing import Optional, Dict, Tuple, List, Any, Union
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
        command: Union[str, List[str]],
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> CommandResult:
        """执行 Mock 命令。"""
        # 支持字符串和列表格式的命令
        if isinstance(command, list):
            command_str = " ".join(command)
        else:
            command_str = command

        self.executed_commands.append(command_str)

        # 检查是否有预设响应（支持子串匹配）
        for cmd_pattern, (exit_code, stdout, stderr) in self.responses.items():
            # 检查是否完全匹配或包含该模式
            if command_str == cmd_pattern or cmd_pattern in command_str:
                return CommandResult(
                    command=command_str,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=10,
                )

        # 返回默认响应
        return CommandResult(
            command=command_str,
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


class MockADBExecutor:
    """Mock ADB 执行器，包装 MockExecutor 以提供 ADBExecutor 接口。"""

    def __init__(self, runner: Optional[MockExecutor] = None):
        self.runner = runner or MockExecutor()
        self._props_cache: Dict[str, Dict[str, str]] = {}
        self.adb_path: str = "adb"
        self.fastboot_path: str = "fastboot"

    def _build_adb_command(
        self,
        action: str,
        *args: str,
        device: Optional[str] = None,
    ) -> str:
        """构建 ADB 命令。"""
        parts = [self.adb_path]
        if device:
            parts.extend(["-s", device])
        parts.append(action)
        parts.extend(args)
        return " ".join(parts)

    def devices(self) -> List[Dict[str, str]]:
        """获取设备列表。"""
        result = self.runner.run(f"{self.adb_path} devices")

        if not result.success:
            return []

        devices = []
        for line in result.stdout.strip().split("\n"):
            if line and not line.startswith("List of devices"):
                parts = line.split("\t")
                if len(parts) >= 2:
                    devices.append({
                        "serial": parts[0],
                        "status": parts[1],
                    })

        return devices

    def shell(
        self,
        command: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """执行 shell 命令。"""
        cmd = self._build_adb_command("shell", command, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def push(
        self,
        local_path: str,
        remote_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """推送文件到设备。"""
        cmd = self._build_adb_command("push", local_path, remote_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def pull(
        self,
        remote_path: str,
        local_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """从设备拉取文件。"""
        cmd = self._build_adb_command("pull", remote_path, local_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def reboot(
        self,
        mode: Optional[str] = None,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """重启设备。"""
        if mode:
            cmd = self._build_adb_command("reboot", mode, device=device)
        else:
            cmd = self._build_adb_command("reboot", device=device)
        return self.runner.run(cmd, timeout=timeout)

    def getprop(
        self,
        prop: Optional[str] = None,
        device: Optional[str] = None,
    ) -> Dict[str, str]:
        """获取设备属性。"""
        if prop:
            result = self.shell(f"getprop {prop}", device=device)
            if result.success:
                return {prop: result.stdout.strip()}
            return {}

        result = self.shell("getprop", device=device, timeout=30)
        if not result.success:
            return {}

        props = {}
        for line in result.stdout.strip().split("\n"):
            match = re.match(r"\[([^\]]+)\]: \[([^\]]+)\]", line)
            if match:
                props[match.group(1)] = match.group(2)

        return props

    def wait_for_device(
        self,
        device: Optional[str] = None,
        timeout: int = 60,
        state: str = "device",
    ) -> CommandResult:
        """等待设备就绪。"""
        cmd = self._build_adb_command("wait-for-device", device=device)
        return self.runner.run(cmd, timeout=timeout)

    def install(
        self,
        package_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """安装 APK。"""
        cmd = self._build_adb_command("install", "-r", package_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def logcat(
        self,
        device: Optional[str] = None,
        output_path: Optional[str] = None,
        timeout: Optional[int] = None,
        clear: bool = False,
    ) -> CommandResult:
        """获取 logcat 日志。"""
        if clear:
            self.shell("logcat -c", device=device)

        cmd = self._build_adb_command("logcat", "-d", device=device)
        result = self.runner.run(cmd, timeout=timeout)

        if output_path and result.success:
            with open(output_path, "w") as f:
                f.write(result.stdout)

        return result

    def set_response(self, command: str, **kwargs):
        """设置响应（代理到内部 runner）。"""
        self.runner.set_response(command, **kwargs)

    def set_props(self, device: Optional[str] = None, props: Dict[str, str] = None):
        """设置预设属性值。"""
        if device:
            self._props_cache[device] = props or {}
        else:
            self._props_cache["default"] = props or {}

    @classmethod
    def with_monkey_responses(cls, success: bool = True) -> "MockADBExecutor":
        """创建带有 Monkey 响应的 Mock ADB 执行器。"""
        executor = cls()
        if success:
            executor.set_response(
                "shell monkey",
                stdout="Events injected: 1000\n:Dropped: 0\n:Crashed: 0\n## Network stats: elapsed time=5s\n"
            )
        else:
            executor.set_response(
                "shell monkey",
                stdout="Events injected: 500\n:Crashed: 1\n** Monkey aborted **\n"
            )
        return executor

    @classmethod
    def upgrade_success_responses(cls) -> "MockADBExecutor":
        """创建升级成功场景的 Mock 响应。"""
        runner = MockExecutor.upgrade_success_responses()
        return cls(runner=runner)

    @classmethod
    def default_device_responses(cls) -> "MockADBExecutor":
        """创建带有默认设备响应的 Mock ADB 执行器。"""
        runner = MockExecutor.default_device_responses()
        return cls(runner=runner)